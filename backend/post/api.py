import os
from django.db.models import Q
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes

from account.models import User, FriendshipRequest
from account.serializers import UserSerializer
from notification.utils import create_notification

from .forms import PostForm
from .models import Post, Like, Comment, Trend, PostAttachment
from .serializers import PostSerializer, PostDetailSerializer, CommentSerializer, TrendSerializer
from .moderation import check_image_nsfw, is_nsfw


@api_view(['GET'])
def post_list(request):
    user_ids = [request.user.id]

    for user in request.user.friends.all():
        user_ids.append(user.id)

    posts = Post.objects.filter(created_by_id__in=user_ids)

    trend = request.GET.get('trend', '')
    if trend:
        posts = posts.filter(body__icontains='#' + trend, is_private=False)

    serializer = PostSerializer(posts, many=True)
    return JsonResponse(serializer.data, safe=False)


@api_view(['GET'])
def post_detail(request, pk):
    user_ids = [request.user.id]

    for user in request.user.friends.all():
        user_ids.append(user.id)

    try:
        post = Post.objects.filter(Q(created_by_id__in=user_ids) | Q(is_private=False)).get(pk=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    return JsonResponse({'post': PostDetailSerializer(post).data})


@api_view(['GET'])
def post_list_profile(request, id):   
    try:
        user = User.objects.get(pk=id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    posts = Post.objects.filter(created_by_id=id)

    if request.user not in user.friends.all():
        posts = posts.filter(is_private=False)

    posts_serializer = PostSerializer(posts, many=True)
    user_serializer = UserSerializer(user)

    can_send_friendship_request = True

    if request.user == user or request.user in user.friends.all():
        can_send_friendship_request = False
    else:
        check1 = FriendshipRequest.objects.filter(created_for=request.user, created_by=user)
        check2 = FriendshipRequest.objects.filter(created_for=user, created_by=request.user)

        if check1.exists() or check2.exists():
            can_send_friendship_request = False

    return JsonResponse({
        'posts': posts_serializer.data,
        'user': user_serializer.data,
        'can_send_friendship_request': can_send_friendship_request
    }, safe=False)


@api_view(['POST'])
def post_create(request):
    form = PostForm(request.POST)
    attachment = None

    # 1. Process Attachment if attached
    if 'image' in request.FILES:
        try:
            attachment = PostAttachment.objects.create(
                image=request.FILES['image'],
                created_by=request.user
            )

            score = check_image_nsfw(attachment.image.path)
            attachment.nsfw_score = score

            if is_nsfw(score):
                # Clean up file and DB entry cleanly
                attachment.image.delete(save=False)
                attachment.delete()

                return JsonResponse(
                    {'error': 'Image violates content guidelines and cannot be posted.'},
                    status=400
                )

            attachment.save()
        except Exception as e:
            print(f"Error processing attachment: {e}")
            if attachment:
                attachment.image.delete(save=False)
                attachment.delete()
            return JsonResponse({'error': 'Failed to process image upload.'}, status=400)

    # 2. Process Post Content
    if form.is_valid():
        post = form.save(commit=False)
        post.created_by = request.user
        post.save()

        if attachment:
            post.attachments.add(attachment)

        user = request.user
        user.posts_count = user.posts.count()
        user.save()

        serializer = PostSerializer(post)
        return JsonResponse(serializer.data, safe=False)
    else:
        # Cleanup uploaded attachment if form text validation failed
        if attachment:
            attachment.image.delete(save=False)
            attachment.delete()

        return JsonResponse({'error': 'Invalid post content.'}, status=400)


@api_view(['POST'])
def post_like(request, pk):
    try:
        post = Post.objects.get(pk=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    if not post.likes.filter(created_by=request.user).exists():
        like = Like.objects.create(created_by=request.user)

        post.likes_count += 1
        post.likes.add(like)
        post.save()

        create_notification(request, 'post_like', post_id=post.id)

        return JsonResponse({'message': 'like created'})
    else:
        return JsonResponse({'message': 'post already liked'})


@api_view(['POST'])
def post_unlike(request, pk):
    try:
        post = Post.objects.get(pk=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    like = post.likes.filter(created_by=request.user).first()
    if like:
        post.likes.remove(like)
        like.delete()

        post.likes_count = max(0, post.likes_count - 1)
        post.save()

        return JsonResponse({'message': 'like removed'})
    else:
        return JsonResponse({'message': 'post not liked yet'})


@api_view(['POST'])
def post_create_comment(request, pk):
    try:
        post = Post.objects.get(pk=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    comment = Comment.objects.create(body=request.data.get('body'), created_by=request.user)

    post.comments.add(comment)
    post.comments_count += 1
    post.save()

    create_notification(request, 'post_comment', post_id=post.id)

    serializer = CommentSerializer(comment)
    return JsonResponse(serializer.data, safe=False)


@api_view(['DELETE'])
def post_delete(request, pk):
    try:
        post = Post.objects.filter(created_by=request.user).get(pk=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found or unauthorized'}, status=404)

    post.delete()

    user = request.user
    user.posts_count = user.posts.count()
    user.save()

    return JsonResponse({'message': 'post deleted'})


@api_view(['DELETE'])
def comment_delete(request, pk):
    try:
        comment = Comment.objects.get(pk=pk)
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)

    post = getattr(comment, "post", None)
    if not post:
        post = Post.objects.filter(comments=comment).first()

    if not post:
        return JsonResponse({'error': 'Post not found for this comment'}, status=404)

    if comment.created_by != request.user and post.created_by != request.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if hasattr(post, "comments") and comment in post.comments.all():
        post.comments.remove(comment)
        post.comments_count = max(0, post.comments_count - 1)
        post.save()

    comment.delete()
    return JsonResponse({'message': 'Comment deleted and count updated'})


@api_view(['POST'])
def post_report(request, pk):
    try:
        post = Post.objects.get(pk=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    post.reported_by_users.add(request.user)
    post.save()

    return JsonResponse({'message': 'post reported'})


@api_view(['GET'])
def get_trends(request):
    serializer = TrendSerializer(Trend.objects.all(), many=True)
    return JsonResponse(serializer.data, safe=False)