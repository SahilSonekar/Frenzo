import requests
from django.conf import settings

NSFW_THRESHOLD = 0.5  # score above this = blocked


def check_image_nsfw(image_path):
    """
    Sends the saved image to Sightengine's nudity detection API
    and returns an NSFW probability score (0.0 = safe, 1.0 = explicit).

    IMPORTANT: We do NOT use 1.0 - nudity['none'] anymore.
    Sightengine's 'none' score also drops for merely "suggestive" content
    (e.g. shirtless men, swimwear, bikinis, cleavage) even when there's
    no actual nudity. This caused false positives on normal beach/gym
    photos. Confirmed via real API output:

        Beach photo (shirtless man, swim shorts):
            sexual_activity: 0.001, sexual_display: 0.001, erotica: 0.001
            suggestive: 0.99, male_chest: 0.99  <- these are NOT explicit
            none: 0.01  <- misleadingly low because of the above

        Genuinely explicit photo:
            sexual_activity: 0.001, sexual_display: 0.06, erotica: 0.99
            none: 0.001

    So instead, we score ONLY off the three classes that represent actual
    explicit/nudity content, and ignore suggestive/context/body-part fields
    entirely (suggestive, mildly_suggestive, male_chest, bikini, swimwear_*,
    cleavage, etc.) since those are meant for a separate, softer
    "sensitive content" tier, not a hard block.
    """
    try:
        with open(image_path, 'rb') as image_file:
            response = requests.post(
                'https://api.sightengine.com/1.0/check.json',
                files={'media': image_file},
                data={
                    'models': 'nudity-2.1',
                    'api_user': settings.SIGHTENGINE_API_USER,
                    'api_secret': settings.SIGHTENGINE_API_SECRET
                }
            )
        result = response.json()
        nudity = result.get('nudity', {})

        # Only genuine explicit-content classes count toward the hard-block score.
        nsfw_score = max(
            nudity.get('sexual_activity', 0.0),
            nudity.get('sexual_display', 0.0),
            nudity.get('erotica', 0.0),
        )

        print(f"\n--- [MODERATION DEBUG] ---")
        print(f"File Path: {image_path}")
        print(f"Calculated NSFW Score: {nsfw_score}")
        print(f"Full Nudity Dict: {nudity}")
        print(f"---------------------------\n")

        return nsfw_score
    except Exception as e:
        print(f"NSFW check failed: {e}")
        return 0.0


def is_nsfw(score, threshold=NSFW_THRESHOLD):
    return score >= threshold