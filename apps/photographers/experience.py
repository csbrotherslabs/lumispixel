from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from datetime import date
import json

KEY = "experience"
def existing(website):
    return (website.theme_content or {}).get(KEY, {"highlights": [], "history": [], "show_highlights": True, "show_history": True})

def parse_experience(request):
    try:
        data = json.loads(request.POST["experience_data"])
        if not isinstance(data, dict):
            raise ValueError()
        result = {}
        for key, limit, fields, required in (
            ("highlights", 6, {"value": 24, "label": 100}, ("value", "label")),
            ("history", 30, {"role": 150, "organization": 150, "start": 10, "end": 10, "description": 2000, "url": 500}, ("role",)),
        ):
            rows = data[key]
            if not isinstance(rows, list) or len(rows) > limit:
                raise ValueError()
            result["show_" + key] = data.get("show_" + key) is True
            result[key] = []
            for row in rows:
                item = {}
                for field, maximum in fields.items():
                    value = row.get(field, "")
                    if not isinstance(value, str) or len(value) > maximum:
                        raise ValueError()
                    item[field] = value.strip()
                if not any(item.values()):
                    continue
                if any(not item[f] for f in required):
                    raise ValidationError("Complete the required experience fields.")
                if key == "history":
                    item["ongoing"] = row.get("ongoing") is True
                    if item["ongoing"]:
                        item["end"] = ""
                    start = date.fromisoformat(item["start"]) if item["start"] else None
                    end = date.fromisoformat(item["end"]) if item["end"] else None
                    if start and end and end < start:
                        raise ValidationError("Experience end date must follow its start date.")
                    if item["url"]:
                        URLValidator(schemes=["http", "https"])(item["url"])
                result[key].append(item)
        return result
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValidationError("Invalid experience content or entry limit exceeded.")

def visible(data):
    return any(data.get("show_" + key) and data.get(key) for key in ("highlights", "history"))
