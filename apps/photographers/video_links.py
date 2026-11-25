"""Normalize supported film links without fetching third-party URLs."""
import re
from urllib.parse import urlsplit, parse_qs
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError


def video_details(value):
    try:
        URLValidator(schemes=["https", "http"])(value)
        u = urlsplit(value)
        if u.username or u.password:
            return None
        host = u.hostname.lower()
        parts = u.path.strip("/").split("/")
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}:
            ident = parts[0] if host == "youtu.be" else (parts[1] if len(parts) == 2 and parts[0] in {"embed", "shorts", "live"} else parse_qs(u.query).get("v", [""])[0])
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", ident):
                return {"provider": "YouTube", "embed": "https://www.youtube-nocookie.com/embed/" + ident, "thumbnail": "https://i.ytimg.com/vi/" + ident + "/hqdefault.jpg"}
        elif host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
            ident = parts[-1]
            if re.fullmatch(r"[0-9]{1,15}", ident):
                return {"provider": "Vimeo", "embed": "https://player.vimeo.com/video/" + ident}
        elif u.scheme == "https" and u.path.lower().endswith(".mp4"):
            return {"provider": "MP4", "source": value}
    except (ValidationError, ValueError, AttributeError):
        pass
    return None
