import json

from pokermda.exporters.manifest import ManifestHand, write_manifest


def test_write_manifest(tmp_path):
    manifest_path = write_manifest(
        tmp_path,
        export_id="export_1",
        hands=[
            ManifestHand(
                hand_id="bovada:1",
                hand_hash="abc",
                file_name="001_bovada_1.txt",
                sanitizer_version="hero-perspective-v1",
            )
        ],
        export_format="bovada_sanitized",
        sanitizer_version="hero-perspective-v1",
    )

    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data["export_id"] == "export_1"
    assert data["hand_count"] == 1
    assert data["hands"][0]["hand_id"] == "bovada:1"

