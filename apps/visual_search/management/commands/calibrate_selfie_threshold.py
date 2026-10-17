"""Offline, model-specific cosine-distance calibration from consented evaluation pairs.

CSV columns: distance,label where label is 'match' or 'nonmatch'.
Use a held-out dataset representing intended users and capture conditions.
No images or embeddings are read or retained by this command.
"""
import csv
import math

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Evaluate candidate selfie distance thresholds from labeled distances."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--max-false-match-rate", type=float, default=0.001)
        parser.add_argument("--min-nonmatches", type=int, default=1000)

    def handle(self, *args, **options):
        target = options["max_false_match_rate"]
        if not 0 < target < 1:
            raise CommandError("False match rate target must be between 0 and 1")
        matches, nonmatches = [], []
        try:
            with open(options["csv_path"], newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    distance = float(row["distance"])
                    if not math.isfinite(distance) or not 0 <= distance <= 2:
                        raise CommandError("Invalid cosine distance")
                    if row["label"] == "match":
                        matches.append(distance)
                    elif row["label"] == "nonmatch":
                        nonmatches.append(distance)
                    else:
                        raise CommandError("Label must be match or nonmatch")
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError("Invalid evaluation CSV") from exc
        if not matches or len(nonmatches) < options["min_nonmatches"]:
            raise CommandError("Insufficient positive or negative evaluation pairs")
        candidates = sorted(set(matches + nonmatches))
        eligible = [t for t in candidates
                    if sum(d <= t for d in nonmatches) / len(nonmatches) <= target]
        if not eligible:
            raise CommandError("No threshold meets the false-match target")
        threshold = max(eligible)
        false_matches = sum(d <= threshold for d in nonmatches)
        true_matches = sum(d <= threshold for d in matches)
        self.stdout.write(
            f"Candidate threshold: {threshold:.6f}; "
            f"empirical FMR: {false_matches}/{len(nonmatches)}; "
            f"TPR: {true_matches}/{len(matches)}. "
            "NOT production-approved: validate on an independent holdout, "
            "across demographics, lighting, devices, and gallery sizes."
        )
