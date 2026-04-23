"""
Gemini API wrapper using the current google-genai SDK.

Model choice — gemini-2.5-flash:
  - Superior character disambiguation vs flash-lite (critical for Z/2, O/0, B/8 etc.)
  - Free tier: 10 RPM, 20 RPD
  - App enforces 7s cooldown between images (~8 RPM max, well under limit)
  - One API call per image (no verification pass) to stay within daily quota

Free tier limits (gemini-2.5-flash):
  - 10 requests per minute  → minimum 6s between requests (app uses 7s)
  - 20 requests per day     → resets midnight Pacific time
"""
import io
import re

from google import genai
from google.genai import types
from PIL import Image

_MODEL = "gemini-2.5-flash"

_VERIFY_PROMPT_TEMPLATE = """You previously extracted these redemption codes from the card image:

{codes}

Your job now is to PROOFREAD each code by looking at the physical card image again, character by character.

Apply the same disambiguation rules:
  Z vs 2  — Z has TWO horizontal bars joined by a diagonal. 2 has ONE bar at the bottom with a curved top.
  Z vs L  — Z has a bar at the top AND bottom. L has NO top bar.
  B vs 8  — B has a straight left edge. 8 is symmetrical.
  S vs 5  — 5 has a FLAT horizontal bar at the very top. S curves continuously with no flat top.
  J vs 2  — J has a hook curving downward at the bottom. 2 has a curved top and flat base.
  C vs E  — E has THREE horizontal bars (top, middle, bottom). C is an open curve with NO bars.
  4 vs E  — 4 has a diagonal stroke and descending vertical. E has only horizontal bars, no diagonal.
  I vs 1  — 1 is a plain vertical stroke. I may have serifs.
  Q vs 0  — Q has a small tail inside/below the circle.

For each code:
  1. Locate it on the card image.
  2. Re-read every character carefully.
  3. Correct any character you are now less confident about.
  4. If a code cannot be found in the image at all, omit it.

Return ONLY the final verified codes, one per line, in the format: XXXX XXXX XXXX XXXX
Do not explain your reasoning. Do not include anything else.
"""

_PROMPT = """You are a precise code-extraction assistant reading redemption codes from Dragon Ball Fusion World trading cards.

Each card has exactly one 16-character code printed in large text near the bottom, formatted as:
    XXXX XXXX XXXX XXXX
(four groups of four characters, separated by spaces, using uppercase letters A-Z and digits 0-9 only).

━━━ CRITICAL: CHARACTER DISAMBIGUATION ━━━
This card font causes frequent misreads. For EVERY character, actively check these pairs:

  Z vs 2  — Count the horizontal bars: Z has TWO flat horizontal bars (top and bottom) joined by a diagonal.
             2 has ONE horizontal bar at the bottom only, with a curved stroke at the top — no diagonal.
             If you see a diagonal stroke connecting two horizontal lines, it is definitely Z not 2.
             In blurry images, default to Z when the top of the character appears flat or angular.

  Z vs L  — Z has a horizontal bar at the TOP and at the BOTTOM with a diagonal between them.
             L has NO top bar — only a vertical stroke on the left and a horizontal bar at the bottom.
             If there is any stroke at the top of the character, it is Z not L.

  B vs 8  — B has a straight vertical stroke on the LEFT side. 8 is symmetrical with no straight edge.

  S vs 5  — Look at the very top of the character: 5 has a flat horizontal bar at the top (like a shelf),
             then drops vertically on the left before curving right at the bottom.
             S has NO flat stroke at the top — it curves continuously like a wave from top to bottom.
             If the top of the character is flat/horizontal, it is 5 not S.
             This is one of the most common misreads in this font — when uncertain, examine the
             top edge: ANY flat or angular top means it is 5. Only call it S if the top is
             unambiguously curved with no flat segment.

  O vs 0  — These are both acceptable in codes. Read whichever is printed.

  I vs 1  — 1 is a simple vertical stroke. I may have serifs/crossbars.

  J vs 2  — J hangs below the baseline with a hook or curve at the bottom; it may have a
             horizontal bar at the top. 2 has a curved top stroke and a flat horizontal
             base — it does NOT hang below the line.
             If the character curves downward at the bottom like a hook, it is J not 2.

  C vs E  — E has THREE horizontal bars: one at the top, one in the middle, one at the bottom.
             C is an open curve with NO horizontal bars — it looks like a parenthesis ( rotated.
             If you can see a middle horizontal stroke, it is E not C.

  4 vs E  — 4 has a diagonal or angled top-left stroke meeting a horizontal crossbar, plus a
             vertical stroke on the right that extends below the crossbar.
             E has only horizontal bars — no diagonal strokes and no descending vertical.
             If the character has an angled or diagonal stroke, it is 4 not E.

  Q vs 0  — Q has a small tail or mark inside/below the circle.

Do not guess — examine the physical shape of each character before deciding.

━━━ INSTRUCTIONS ━━━
1. Find every redemption code visible in the image (there may be multiple cards).
2. Apply the character checks above to each character in each code.
3. Return ONLY the codes, one per line, exactly as: XXXX XXXX XXXX XXXX
4. If no codes are visible, return exactly: NONE
"""

# Matches XXXX XXXX XXXX XXXX — groups of 4 alphanumeric separated by space or dash
_CODE_RE = re.compile(
    r"\b([A-Z0-9]{4})[\s\-]([A-Z0-9]{4})[\s\-]([A-Z0-9]{4})[\s\-]([A-Z0-9]{4})\b"
)


def _pil_to_part(image: Image.Image) -> types.Part:
    """Convert a PIL image to a Gemini-compatible Part (inline bytes, JPEG)."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)  # higher quality = better OCR accuracy
    return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def extract_codes(self, image: Image.Image) -> list[str]:
        """
        Send a PIL image to Gemini and return a deduplicated list of card codes
        found in the image, formatted as 'XXXX XXXX XXXX XXXX'.
        """
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=[_pil_to_part(image), _PROMPT],
        )
        return _parse_response(response.text)

    def verify_codes(self, image: Image.Image, codes: list[str]) -> list[str]:
        """
        Proofread a list of extracted codes against the original image.

        Sends the image + the extracted codes back to Gemini and asks it to
        re-examine each code character by character, correcting any mistakes.
        Returns the verified (and possibly corrected) code list.

        Counts as one additional API request per image — keep rate limits in mind.
        Returns the original codes unchanged if the verification call fails.
        """
        if not codes:
            return codes
        codes_text = "\n".join(codes)
        prompt = _VERIFY_PROMPT_TEMPLATE.format(codes=codes_text)
        try:
            response = self._client.models.generate_content(
                model=_MODEL,
                contents=[_pil_to_part(image), prompt],
            )
            verified = _parse_response(response.text)
            return verified if verified else codes
        except Exception:
            # If verification fails for any reason, return the original codes
            # so the scan result is not silently dropped.
            return codes

    def validate_key(self) -> str | None:
        """
        Send a minimal text-only request to verify the API key works.
        Returns None on success, or an error message string on failure.
        """
        try:
            self._client.models.generate_content(
                model=_MODEL,
                contents="Reply with the single word: OK",
            )
            return None
        except Exception as exc:
            return str(exc)


def _parse_response(text: str) -> list[str]:
    """Extract and deduplicate card codes from a Gemini response string."""
    text = text.strip().upper()
    if not text or text == "NONE":
        return []

    codes: list[str] = []
    seen: set[str] = set()

    for match in _CODE_RE.finditer(text):
        code = f"{match.group(1)} {match.group(2)} {match.group(3)} {match.group(4)}"
        if code not in seen:
            seen.add(code)
            codes.append(code)

    return codes
