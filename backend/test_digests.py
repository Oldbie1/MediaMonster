import unittest
import server

class DigestTests(unittest.TestCase):
    def description(self, digest):
        return "MediaType: application/vnd.oci.image.index.v1+json\nDigest: sha256:" + digest * 64 + "\n"

    def test_current_containerd_index_is_not_config_digest(self):
        image = {"Id": "sha256:" + "a"*64, "Descriptor": {"digest": "sha256:"+"a"*64,
                 "mediaType": "application/vnd.oci.image.index.v1+json"}}
        self.assertFalse(server.registry_update_available(image, self.description("a")))

    def test_changed_index_is_update(self):
        image = {"Descriptor": {"digest": "sha256:"+"a"*64,
                 "mediaType": "application/vnd.oci.image.index.v1+json"}}
        self.assertTrue(server.registry_update_available(image, self.description("b")))

    def test_legacy_config_id_is_ignored(self):
        image = {"Id": "sha256:"+"c"*64, "RepoDigests": ["repo@sha256:"+"a"*64]}
        self.assertFalse(server.registry_update_available(image, self.description("a")))

    def test_no_comparable_digest_is_unknown(self):
        with self.assertRaises(ValueError):
            server.registry_update_available({"Id": "sha256:"+"c"*64}, self.description("a"))

    def test_registry_error_is_not_an_update(self):
        with self.assertRaises(ValueError):
            server.registry_update_available({}, "429 Too Many Requests")
