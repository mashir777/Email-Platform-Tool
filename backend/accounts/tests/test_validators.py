from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.validators import validate_avatar_file, validate_phone_number


class ValidatorsTestCase(SimpleTestCase):
    def test_valid_phone_number_international(self):
        validate_phone_number("+14155552671")

    def test_valid_phone_number_local(self):
        validate_phone_number("03001234567")
        validate_phone_number("0300-1234567")
        validate_phone_number("+92 300 1234567")

    def test_invalid_phone_number(self):
        with self.assertRaises(ValidationError):
            validate_phone_number("abc")
        with self.assertRaises(ValidationError):
            validate_phone_number("12345")

    def test_avatar_size_limit(self):
        large_file = SimpleUploadedFile(
            "big.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_avatar_file(large_file)

    def test_avatar_invalid_type(self):
        invalid_file = SimpleUploadedFile(
            "file.txt",
            b"text",
            content_type="text/plain",
        )
        with self.assertRaises(ValidationError):
            validate_avatar_file(invalid_file)
