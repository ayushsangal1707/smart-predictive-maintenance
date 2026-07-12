"""
Registers a model trained by predictions/ml/train.py into the database as
a ModelVersion, reading its accompanying metadata JSON.

This is the bridge between "offline training" (Prompt 5's train.py, run
manually / outside the request cycle) and the Django app knowing which
model is currently active (predict.py loads whichever ModelVersion has
is_active=True).

Usage:
    python manage.py load_model_version v1
    python manage.py load_model_version v1 --activate=false
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from predictions.models import ModelVersion

MODEL_REGISTRY_DIR = Path(__file__).resolve().parents[2] / "ml" / "model_registry"


class Command(BaseCommand):
    help = "Registers a trained model (from predictions/ml/model_registry/) as a ModelVersion in the database."

    def add_arguments(self, parser):
        parser.add_argument("version_name", type=str, help="e.g. v1 (matches model_v1.pkl / model_v1_metadata.json)")
        parser.add_argument(
            "--activate", type=str, default="true",
            help="Whether to mark this version active (deactivating others). Default: true.",
        )

    def handle(self, *args, **options):
        version_name = options["version_name"]
        activate = options["activate"].lower() != "false"

        metadata_path = MODEL_REGISTRY_DIR / f"model_{version_name}_metadata.json"
        model_path = MODEL_REGISTRY_DIR / f"model_{version_name}.pkl"

        if not metadata_path.exists():
            raise CommandError(f"Metadata file not found: {metadata_path}")
        if not model_path.exists():
            raise CommandError(f"Model file not found: {model_path}")

        with open(metadata_path) as f:
            metadata = json.load(f)

        model_version, created = ModelVersion.objects.update_or_create(
            version_name=metadata["version_name"],
            defaults={
                "algorithm": metadata["algorithm"],
                "trained_at": parse_datetime(metadata["trained_at"]),
                "file_path": model_path.name,
                "feature_columns": metadata["feature_columns"],
                "metrics": metadata["metrics"],
                "is_active": activate,
            },
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} ModelVersion '{model_version.version_name}' "
            f"({model_version.algorithm}), active={model_version.is_active}."
        ))
