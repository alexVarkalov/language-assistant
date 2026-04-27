from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)
MAX_TRANSLATION_OPTIONS = 3


class TranslationError(Exception):
    pass


async def translate_text(
    *,
    text: str,
    source_lang: str,
    target_lang: str,
    translator: str,
    deepl_api_key: str | None,
    deepl_plan: str = "auto",
    client: httpx.AsyncClient,
) -> str:
    options = await translate_text_options(
        text=text,
        source_lang=source_lang,
        target_lang=target_lang,
        translator=translator,
        deepl_api_key=deepl_api_key,
        deepl_plan=deepl_plan,
        client=client,
    )
    return options[0]


async def translate_text_options(
    *,
    text: str,
    source_lang: str,
    target_lang: str,
    translator: str,
    deepl_api_key: str | None,
    deepl_plan: str = "auto",
    client: httpx.AsyncClient,
) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        raise TranslationError("empty text")

    if translator != "deepl" or not deepl_api_key:
        raise TranslationError("DeepL translator is required and must be configured")
    return await _deepl_options(
        trimmed,
        source_lang,
        target_lang,
        deepl_api_key,
        client,
        plan=deepl_plan,
    )


DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"


def _deepl_error_detail(response: httpx.Response) -> str:
    raw = (response.text or "").strip()
    if not raw:
        return "empty response body"
    try:
        payload = response.json()
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    except ValueError:
        pass
    return raw[:400]


async def _deepl_options(
    text: str,
    source_lang: str,
    target_lang: str,
    api_key: str,
    client: httpx.AsyncClient,
    *,
    plan: str,
) -> list[str]:
    """
    DeepL Free API keys only work with api-free.deepl.com; paid Pro API keys with api.deepl.com.
    Both may return HTTP 403 for wrong host *or* for an invalid/non-API key — check DeepL's JSON message.
    """
    if plan == "free":
        hosts = (DEEPL_FREE_URL,)
    elif plan == "pro":
        hosts = (DEEPL_PRO_URL,)
    else:
        hosts = (DEEPL_FREE_URL, DEEPL_PRO_URL)

    last_error: str | None = None
    free_403_detail: str | None = None
    auth_header = {"Authorization": f"DeepL-Auth-Key {api_key.strip()}"}
    form_body = {
        "text": text,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }
    for url in hosts:
        try:
            # Legacy auth_key in form body was deprecated (Nov 2025); use header auth only.
            response = await client.post(
                url,
                headers=auth_header,
                data=form_body,
                timeout=20.0,
            )
            if response.status_code in (401, 403):
                detail = _deepl_error_detail(response)
                last_error = f"HTTP {response.status_code} ({url}): {detail}"
                logger.warning("DeepL auth failed: %s", last_error)

                # Paid endpoint rejects Free-plan keys with “use api-free.deepl.com”.
                if response.status_code == 403 and url == DEEPL_PRO_URL and "api-free" in detail.lower():
                    if plan == "pro":
                        raise TranslationError(
                            "This DeepL key is for the Free API only. "
                            "Set DEEPL_PLAN=free in your .env (or remove DEEPL_PLAN=pro)."
                        ) from None
                    if plan == "auto":
                        extra = f" Free endpoint said: {free_403_detail}" if free_403_detail else ""
                        raise TranslationError(
                            "This key only works on the Free API host. "
                            "Set DEEPL_PLAN=free (default) and ensure DEEPL_API_KEY is correct." + extra
                        ) from None

                # Free endpoint may tell you to use the paid host for your subscription.
                if response.status_code == 403 and url == DEEPL_FREE_URL and "api.deepl.com" in detail.lower():
                    raise TranslationError(
                        "DeepL says use the paid API host. Set DEEPL_PLAN=pro in your .env."
                    ) from None

                if response.status_code == 403 and url == DEEPL_FREE_URL:
                    free_403_detail = detail

                if response.status_code == 403 and plan == "auto" and len(hosts) > 1:
                    continue
                raise TranslationError(f"DeepL: {detail}") from None
            response.raise_for_status()
            payload = response.json()
            translations = payload.get("translations") or []
            if not translations:
                raise TranslationError("deepl returned no translations")
            options = [str(item.get("text", "")).strip() for item in translations]
            options = _normalize_options(options)
            if options:
                return options
            raise TranslationError("deepl returned empty translation options")
        except TranslationError:
            raise
        except httpx.HTTPStatusError as exc:
            detail = _deepl_error_detail(exc.response)
            last_error = f"HTTP {exc.response.status_code}: {detail}"
            logger.warning("DeepL attempt failed (%s): %s", url, last_error)
        except httpx.HTTPError as exc:
            last_error = str(exc)
            logger.warning("DeepL attempt failed (%s): %s", url, last_error)
    msg = f"DeepL translation failed: {last_error or 'unknown error'}"
    raise TranslationError(msg)


def _normalize_options(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if len(result) >= MAX_TRANSLATION_OPTIONS:
            break
    return result
