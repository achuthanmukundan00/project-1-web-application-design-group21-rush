# tests/test_app.py

import unittest
from unittest.mock import patch, MagicMock, ANY
import json
import os
from dotenv import load_dotenv
from itsdangerous import BadSignature, SignatureExpired
from flask_jwt_extended import create_access_token

# Load environment variables from .env.test
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.test"))

from app import create_app


class TestFlaskApp(unittest.TestCase):
    def setUp(self):
        # Create a test app instance with testing configuration
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Access the pending_registrations from the app instance
        self.pending_registrations = self.app.pending_registrations
        self.pending_registrations.clear()

        # Generate a test JWT token and set it in headers for authenticated requests
        with self.app.app_context():
            access_token = create_access_token(identity="testuser")
            self.headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }


    @patch("app.send_verification_email")
    @patch("app.scan_users_by_attribute")
    def test_pre_register_success(self, mock_scan_users, mock_send_verification_email):
        # Mock scan_users_by_attribute to return no existing user
        mock_scan_users.return_value = []

        # Mock send_verification_email to return a token
        mock_send_verification_email.return_value = "test-token"

        # Define the user data
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123",
            "wishlist": "Books, Electronics",
            "categories": "Fiction, Gadgets",
            "location": "New York",
        }

        # Send POST request to /pre_register
        response = self.client.post('/api/users/pre_register',
                                    data=json.dumps(user_data),
                                    content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Verification email sent", response.data)

        # Verify that the pending_registrations is updated
        self.assertIn("test@example.com", self.pending_registrations)
        self.assertEqual(
            self.pending_registrations["test@example.com"]["username"], "testuser"
        )

        # Verify that send_verification_email was called with the correct email, username, and serializer
        mock_send_verification_email.assert_called_with(
            "test@example.com", "testuser", self.app.serializer
        )

    @patch("app.scan_users_by_attribute")
    def test_pre_register_existing_username(self, mock_scan_users):
        # Mock scan_users_by_attribute to return existing username
        def side_effect(attribute, value):
            if attribute == "username" and value == "testuser":
                return [{"username": "testuser"}]
            return []

        mock_scan_users.side_effect = side_effect

        # Define the user data
        user_data = {
            "username": "testuser",
            "email": "newemail@example.com",
            "password": "TestPassword123",
            "wishlist": "",
            "categories": "",
            "location": "",
        }

        # Send POST request to /pre_register
        response = self.client.post('/api/users/pre_register',
                                    data=json.dumps(user_data),
                                    content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"User with this username already exists", response.data)

    @patch("app.scan_users_by_attribute")
    def test_pre_register_existing_email(self, mock_scan_users):
        # Mock scan_users_by_attribute to return existing email
        def side_effect(attribute, value):
            if attribute == "email" and value == "test@example.com":
                return [{"email": "test@example.com"}]
            return []

        mock_scan_users.side_effect = side_effect

        # Define the user data
        user_data = {
            "username": "newuser",
            "email": "test@example.com",
            "password": "TestPassword123",
            "wishlist": "",
            "categories": "",
            "location": "",
        }

        # Send POST request to /pre_register
        response = self.client.post('/api/users/pre_register',
                                    data=json.dumps(user_data),
                                    content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"User with this email already exists", response.data)

    @patch("app.scan_users_by_attribute")
    def test_pre_register_existing_username_and_email(self, mock_scan_users):
        # Mock scan_users_by_attribute to return existing username and email
        def side_effect(attribute, value):
            if (attribute == "username" and value == "testuser") or (
                attribute == "email" and value == "test@example.com"
            ):
                return [{"username": "testuser", "email": "test@example.com"}]
            return []

        mock_scan_users.side_effect = side_effect

        # Define the user data
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123",
            "wishlist": "",
            "categories": "",
            "location": "",
        }

        # Send POST request to /pre_register
        response = self.client.post('/api/users/pre_register',
                                    data=json.dumps(user_data),
                                    content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            b"User with this username and email already exists", response.data
        )

    def test_verify_email_success(self):
        with patch.object(
            self.app.serializer, "loads", return_value="test@example.com"
        ), patch("app.upload_to_user_table") as mock_upload_to_user_table:

            # Add a pending registration
            self.pending_registrations["test@example.com"] = {
                "username": "testuser",
                "password": "TestPassword123",
                "wishlist": "",
                "categories": "",
                "location": "",
            }

            # Mock upload_to_user_table to return True
            mock_upload_to_user_table.return_value = True

            # Send GET request to /verify_email/<token>
            response = self.client.get('/api/users/verify_email/test-token')

            # Check the response
            self.assertEqual(response.status_code, 201)
            self.assertIn(
                b"Email verified and account created successfully", response.data
            )

            # Verify that the user was created in database
            mock_upload_to_user_table.assert_called()
            args, kwargs = mock_upload_to_user_table.call_args
            user_data = args[0]
            self.assertEqual(user_data["username"], "testuser")
            self.assertEqual(user_data["email"], "test@example.com")
            self.assertEqual(user_data["wishlist"], "")
            self.assertEqual(user_data["categories"], "")
            self.assertEqual(user_data["location"], "")
            self.assertTrue(user_data["email_verified"])

            # Verify that the pending registration was removed
            self.assertNotIn("test@example.com", self.pending_registrations)

    def test_verify_email_invalid_token(self):
        with patch.object(
            self.app.serializer, "loads", side_effect=BadSignature("Invalid signature")
        ):
            # Send GET request to /verify_email/<invalid_token>
            response = self.client.get('/api/users/verify_email/invalid-token')

            # Check the response
            self.assertEqual(response.status_code, 400)
            self.assertIn(b"Verification link is invalid or has expired", response.data)

    def test_verify_email_expired_token(self):
        with patch.object(
            self.app.serializer,
            "loads",
            side_effect=SignatureExpired("Signature expired"),
        ):
            # Send GET request to /verify_email/<expired_token>
            response = self.client.get('/api/users/verify_email/expired-token')

            # Check the response
            self.assertEqual(response.status_code, 400)
            self.assertIn(b"Verification link is invalid or has expired", response.data)

    def test_verify_email_no_pending_registration(self):
        with patch.object(
            self.app.serializer, "loads", return_value="nonexistent@example.com"
        ):
            # Ensure no pending registration exists
            self.pending_registrations.pop("nonexistent@example.com", None)

            # Send GET request to /verify_email/<token>
            response = self.client.get('/api/users/verify_email/test-token')

            # Check the response
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                b"Registration request not found or has expired", response.data
            )

    @patch("app.send_verification_email")
    def test_resend_verification_success(self, mock_send_verification_email):
        # Add a pending registration
        self.pending_registrations["test@example.com"] = {
            "username": "testuser",
            "password": "TestPassword123",
            "wishlist": "",
            "categories": "",
            "location": "",
        }

        # Mock send_verification_email to return a token
        mock_send_verification_email.return_value = "new-test-token"

        # Define the resend data
        resend_data = {"email": "test@example.com"}

        # Send POST request to /resend_verification
        response = self.client.post('/api/users/resend_verification',
                                    data=json.dumps(resend_data),
                                    content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Verification email resent", response.data)

        # Verify that send_verification_email was called with the correct email, username, and serializer
        mock_send_verification_email.assert_called_with(
            "test@example.com", "testuser", self.app.serializer
        )

    def test_resend_verification_no_pending_registration(self):
        # Define the resend data with no pending registration
        resend_data = {"email": "nonexistent@example.com"}

        # Send POST request to /resend_verification
        response = self.client.post('/api/users/resend_verification',
                                    data=json.dumps(resend_data),
                                    content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"No pending registration for this email", response.data)
    
    @patch("app.get_user_by_id")
    @patch("app.update_user")
    def test_add_to_wishlist(self, mock_update_user, mock_get_user_by_id):
        # Mock the user retrieval and update functions
        mock_get_user_by_id.return_value = {"id": "testuser", "wishlist": []}
        mock_update_user.return_value = True

        # Define data for the request
        data = {"listingId": "test-listing-id"}

        # Make the POST request to add to wishlist
        response = self.client.post(
            "/api/users/wishlist", headers=self.headers, data=json.dumps(data)
        )

        # Verify the response status code and content
        self.assertEqual(
            response.status_code, 200, f"Unexpected status code: {response.status_code}"
        )
        self.assertIn(
            "Listing added to wishlist", response.get_json().get("message", "")
        )

    def test_add_to_wishlist_missing_listing_id(self):
        # Make the POST request without the listingId
        response = self.client.post(
            "/api/users/wishlist", headers=self.headers, content_type="application/json"
        )

        # Verify the response status code
        self.assertEqual(response.status_code, 400, f"Unexpected status code: {response.status_code}")

        # Attempt to parse JSON and provide debugging information if it fails
        try:
            response_json = response.get_json()
            self.assertIsNotNone(response_json, f"Expected JSON response, got None. Raw response: {response.data}")
            self.assertIn("Listing ID is required", response_json.get("error", ""))
        except Exception as e:
            self.fail(f"Response is not JSON or is missing expected error message: {e}. Raw response: {response.data}")

    @patch('app.scan_users_by_attribute')
    @patch('app.check_password_hash')
    def test_login_success(self, mock_check_password_hash, mock_scan_users):
        # Mock scan_users_by_attribute to return a list containing a user
        user_data = {
            "id": "testuser_id",
            "email": "test@example.com",
            "password": "hashed_password",
            "email_verified": True
        }
        mock_scan_users.return_value = [user_data]  # Return a list of users

        # Mock check_password_hash to return True
        mock_check_password_hash.return_value = True

        # Prepare login data
        login_data = {
            "email": "test@example.com",
            "password": "TestPassword123"
        }

        # Send POST request to /api/users/login
        response = self.client.post(
            '/api/users/login',
            data=json.dumps(login_data),
            content_type='application/json'
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertIn("access_token", response_json)
        self.assertEqual(response_json["message"], "Login successful")

    @patch('app.scan_users_by_attribute')
    @patch('app.check_password_hash')
    def test_login_invalid_credentials(self, mock_check_password_hash, mock_scan_users):
        # Mock scan_users_by_attribute to return a list containing a user
        user_data = {
            "id": "testuser_id",
            "email": "test@example.com",
            "password": "hashed_password",
            "email_verified": True
        }
        mock_scan_users.return_value = [user_data]  # Return a list of users

        # Mock check_password_hash to return False (invalid password)
        mock_check_password_hash.return_value = False

        # Prepare login data with wrong password
        login_data = {
            "email": "test@example.com",
            "password": "WrongPassword"
        }

        # Send POST request to /api/users/login
        response = self.client.post(
            '/api/users/login',
            data=json.dumps(login_data),
            content_type='application/json'
        )

        # Check the response
        self.assertEqual(response.status_code, 401)
        response_json = response.get_json()
        self.assertEqual(response_json["error"], "Invalid email or password")

    @patch('app.scan_users_by_attribute')
    @patch('app.check_password_hash')
    def test_login_unverified_email(self, mock_check_password_hash, mock_scan_users):
        # Mock scan_users_by_attribute to return a list containing a user
        user_data = {
            "id": "testuser_id",
            "email": "test@example.com",
            "password": "hashed_password",
            "email_verified": False  # Email not verified
        }
        mock_scan_users.return_value = [user_data]  # Return a list of users

        # Mock check_password_hash to return True
        mock_check_password_hash.return_value = True

        # Prepare login data
        login_data = {
            "email": "test@example.com",
            "password": "TestPassword123"
        }

        # Send POST request to /api/users/login
        response = self.client.post(
            '/api/users/login',
            data=json.dumps(login_data),
            content_type='application/json'
        )

        # Check the response
        self.assertEqual(response.status_code, 403)
        response_json = response.get_json()
        self.assertEqual(response_json["error"], "Email not verified")

    def test_logout_success(self):
        # Use the token from self.headers to log out
        response = self.client.post(
            '/api/users/logout',
            headers=self.headers
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertEqual(response_json["message"], "Successfully logged out")

        # Try to use the same token to access a protected endpoint
        response = self.client.get(
            '/api/users/user_id',
            headers=self.headers
        )

        # Check the response
        self.assertEqual(response.status_code, 401)
        response_json = response.get_json()
        self.assertIn("msg", response_json)
        self.assertIn("Token has been revoked", response_json["msg"])

    def test_logout_with_revoked_token(self):
        # First, log out to revoke the token
        response = self.client.post(
            '/api/users/logout',
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)

        # Attempt to log out again with the same token
        response = self.client.post(
            '/api/users/logout',
            headers=self.headers
        )

        # Check the response
        self.assertEqual(response.status_code, 401)
        response_json = response.get_json()
        self.assertIn("msg", response_json)
        self.assertIn("Token has been revoked", response_json["msg"])

    def test_protected_endpoint_without_token(self):
        # Attempt to access a protected endpoint without a token
        response = self.client.get('/api/users/user_id')

        # Check the response
        self.assertEqual(response.status_code, 401)
        response_json = response.get_json()
        self.assertIn("msg", response_json)
        self.assertIn("Missing Authorization Header", response_json["msg"])
    
    # Add new test cases here for the check_wishlist endpoint
    @patch("app.get_user_by_id")
    def test_check_wishlist_listing_present(self, mock_get_user_by_id):
        # Mock get_user_by_id to return a user with a wishlist containing the listing
        mock_get_user_by_id.return_value = {
            "id": "testuser",
            "wishlist": ["listing_1", "listing_2"]
        }

        # Send POST request to check if "listing_1" is in the wishlist
        response = self.client.post(
            "/api/users/wishlist/check",
            headers=self.headers,
            data=json.dumps({"listingId": "listing_1"})
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["is_in_wishlist"])

    @patch("app.get_user_by_id")
    def test_check_wishlist_listing_not_present(self, mock_get_user_by_id):
        # Mock get_user_by_id to return a user with a wishlist that does not contain the listing
        mock_get_user_by_id.return_value = {
            "id": "testuser",
            "wishlist": ["listing_2", "listing_3"]
        }

        # Send POST request to check if "listing_1" is in the wishlist
        response = self.client.post(
            "/api/users/wishlist/check",
            headers=self.headers,
            data=json.dumps({"listingId": "listing_1"})
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["is_in_wishlist"])

    @patch("app.get_user_by_id")
    def test_check_wishlist_missing_listing_id(self, mock_get_user_by_id):
        # Mock get_user_by_id to return a user
        mock_get_user_by_id.return_value = {
            "id": "testuser",
            "wishlist": ["listing_2", "listing_3"]
        }

        # Send POST request without listingId
        response = self.client.post(
            "/api/users/wishlist/check",
            headers=self.headers,
            data=json.dumps({})
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn("Listing ID is required", response.get_json()["error"])

    @patch("app.get_user_by_id")
    def test_check_wishlist_user_not_found(self, mock_get_user_by_id):
        # Mock get_user_by_id to return None, simulating a user not found
        mock_get_user_by_id.return_value = None

        # Send POST request to check if "listing_1" is in the wishlist
        response = self.client.post(
            "/api/users/wishlist/check",
            headers=self.headers,
            data=json.dumps({"listingId": "listing_1"})
        )

        # Check the response
        self.assertEqual(response.status_code, 404)
        self.assertIn("User not found", response.get_json()["error"])

    @patch("app.get_user_by_id")
    def test_get_user_info_success(self, mock_get_user_by_id):
        # Mock the user retrieval to return user information
        mock_get_user_by_id.return_value = {"id": "testuser", "username": "testuser", "email": "test@example.com"}

        # Make the GET request to retrieve user info
        response = self.client.get("/api/users/current_user_info", headers=self.headers)

        # Verify the response status code and content
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json.get("id"), "testuser")
        self.assertEqual(response.json.get("email"), "test@example.com")

    @patch("app.get_user_by_id")
    def test_get_user_info_user_not_found(self, mock_get_user_by_id):
        # Mock the user retrieval to return None (user not found)
        mock_get_user_by_id.return_value = None

        # Make the GET request to retrieve user info
        response = self.client.get("/api/users/current_user_info", headers=self.headers)

        # Verify the response status code and error message
        self.assertEqual(response.status_code, 404)
        self.assertIn("User not found", response.json.get("error", ""))
        

    # Unit tests for change_password feature
    @patch("app.update_user")
    @patch("app.check_password_hash")
    @patch("app.get_user_by_id")
    def test_change_password_success(
        self, mock_get_user_by_id, mock_check_password_hash, mock_update_user
    ):
        # Simulate user data
        user_data = {
            "id": "testuser_id",
            "username": "testuser",
            "password": "hashed_old_password",  # Old hashed password
        }
        # Mock get_user_by_id to return user data
        mock_get_user_by_id.return_value = user_data

        # Mock check_password_hash to return True when checking old password
        mock_check_password_hash.return_value = True

        # Mock update_user to return True
        mock_update_user.return_value = True

        # Prepare data
        data = {
            "old_password": "OldPassword123",
            "new_password": "NewPassword456",
        }

        # Generate a token with identity "testuser_id"
        with self.app.app_context():
            access_token = create_access_token(identity="testuser_id")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Send POST request to /api/users/change_password
        response = self.client.post(
            "/api/users/change_password",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertEqual(response_json["message"], "Password changed successfully")

        # Verify that check_password_hash was called with correct parameters
        mock_check_password_hash.assert_called_with(
            "hashed_old_password", "OldPassword123"
        )

        # Verify that update_user was called with correct parameters
        mock_update_user.assert_called_with("testuser_id", {"password": ANY})

    @patch("app.check_password_hash")
    @patch("app.get_user_by_id")
    def test_change_password_incorrect_old_password(
        self, mock_get_user_by_id, mock_check_password_hash
    ):
        # Simulate user data
        user_data = {
            "id": "testuser_id",
            "username": "testuser",
            "password": "hashed_old_password",  # Old hashed password
        }
        # Mock get_user_by_id to return user data
        mock_get_user_by_id.return_value = user_data

        # Mock check_password_hash to return False when checking old password
        mock_check_password_hash.return_value = False

        # Prepare data
        data = {
            "old_password": "WrongOldPassword",
            "new_password": "NewPassword456",
        }

        # Generate a token with identity "testuser_id"
        with self.app.app_context():
            access_token = create_access_token(identity="testuser_id")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Send POST request to /api/users/change_password
        response = self.client.post(
            "/api/users/change_password",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 401)
        response_json = response.get_json()
        self.assertEqual(response_json["error"], "Incorrect old password")

        # Verify that check_password_hash was called with correct parameters
        mock_check_password_hash.assert_called_with(
            "hashed_old_password", "WrongOldPassword"
        )

    @patch("app.check_password_hash")
    @patch("app.get_user_by_id")
    def test_change_password_same_old_and_new_password(
        self, mock_get_user_by_id, mock_check_password_hash
    ):
        # Simulate user data
        user_data = {
            "id": "testuser_id",
            "username": "testuser",
            "password": "hashed_old_password",  # Old hashed password
        }
        # Mock get_user_by_id to return user data
        mock_get_user_by_id.return_value = user_data

        # Mock check_password_hash to return True when checking old password
        mock_check_password_hash.return_value = True

        # Prepare data where old_password and new_password are the same
        data = {
            "old_password": "SamePassword",
            "new_password": "SamePassword",
        }

        # Generate a token with identity "testuser_id"
        with self.app.app_context():
            access_token = create_access_token(identity="testuser_id")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Send POST request to /api/users/change_password
        response = self.client.post(
            "/api/users/change_password",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 400)
        response_json = response.get_json()
        self.assertEqual(response_json["error"], "New password must be different")

    def test_change_password_missing_fields(self):
        # Prepare data missing old_password and new_password
        data = {}

        # Generate a token with identity "testuser_id"
        with self.app.app_context():
            access_token = create_access_token(identity="testuser_id")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Send POST request to /api/users/change_password
        response = self.client.post(
            "/api/users/change_password",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 400)
        response_json = response.get_json()
        self.assertEqual(
            response_json["error"], "Old password and new password are required"
        )

    # Unit tests for forgot_password feature
    @patch("app.send_password_reset_email")
    @patch("app.scan_users_by_attribute")
    def test_forgot_password_success(
        self, mock_scan_users, mock_send_password_reset_email
    ):
        # Mock scan_users_by_attribute to return user
        user_data = {
            "id": "testuser_id",
            "username": "testuser",
            "email": "test@example.com",
        }
        mock_scan_users.return_value = [user_data]

        # Mock send_password_reset_email to return token
        mock_send_password_reset_email.return_value = "test-reset-token"

        # Prepare data
        data = {
            "email": "test@example.com"
        }

        # Send POST request to /api/users/forgot_password
        response = self.client.post(
            "/api/users/forgot_password",
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertEqual(
            response_json["message"],
            "If the email exists, a reset link has been sent.",
        )

        # Verify that send_password_reset_email was called
        mock_send_password_reset_email.assert_called_with(
            "test@example.com", "testuser", self.app.serializer
        )

    def test_forgot_password_email_not_provided(self):
        # Prepare data without email
        data = {}

        # Send POST request to /api/users/forgot_password
        response = self.client.post(
            "/api/users/forgot_password",
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 400)
        response_json = response.get_json()
        self.assertEqual(response_json["error"], "Email is required")

    @patch("app.scan_users_by_attribute")
    def test_forgot_password_user_not_found(self, mock_scan_users):
        # Mock scan_users_by_attribute to return empty list
        mock_scan_users.return_value = []

        # Prepare data
        data = {
            "email": "nonexistent@example.com"
        }

        # Send POST request to /api/users/forgot_password
        response = self.client.post(
            "/api/users/forgot_password",
            data=json.dumps(data),
            content_type="application/json",
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertEqual(
            response_json["message"],
            "If the email exists, a reset link has been sent.",
        )

    # Unit tests for reset_password feature
    @patch("app.update_user")
    @patch("app.scan_users_by_attribute")
    def test_reset_password_success(self, mock_scan_users, mock_update_user):
        # Mock serializer.loads to return email
        with patch.object(self.app.serializer, "loads", return_value="test@example.com"):
            # Mock scan_users_by_attribute to return user
            user_data = {
                "id": "testuser_id",
                "email": "test@example.com",
            }
            mock_scan_users.return_value = [user_data]

            # Mock update_user to return True
            mock_update_user.return_value = True

            # Prepare data
            data = {
                "new_password": "NewPassword123"
            }

            # Send POST request to /api/users/reset_password/<token>
            response = self.client.post(
                "/api/users/reset_password/test-token",
                data=json.dumps(data),
                content_type="application/json",
            )

            # Check response
            self.assertEqual(response.status_code, 200)
            response_json = response.get_json()
            self.assertEqual(
                response_json["message"], "Password has been reset successfully"
            )

            # Verify that update_user was called with correct parameters
            mock_update_user.assert_called_with("testuser_id", {"password": ANY})

    def test_reset_password_invalid_token(self):
        # Mock serializer.loads to raise BadSignature
        with patch.object(
            self.app.serializer, "loads", side_effect=BadSignature("Invalid signature")
        ):
            # Prepare data
            data = {
                "new_password": "NewPassword123"
            }

            # Send POST request to /api/users/reset_password/<invalid_token>
            response = self.client.post(
                "/api/users/reset_password/invalid-token",
                data=json.dumps(data),
                content_type="application/json",
            )

            # Check response
            self.assertEqual(response.status_code, 400)
            response_json = response.get_json()
            self.assertEqual(response_json["error"], "Invalid reset link")

    def test_reset_password_expired_token(self):
        # Mock serializer.loads to raise SignatureExpired
        with patch.object(
            self.app.serializer, "loads", side_effect=SignatureExpired("Signature expired")
        ):
            # Prepare data
            data = {
                "new_password": "NewPassword123"
            }

            # Send POST request to /api/users/reset_password/expired-token
            response = self.client.post(
                "/api/users/reset_password/expired-token",
                data=json.dumps(data),
                content_type="application/json",
            )

            # Check response
            self.assertEqual(response.status_code, 400)
            response_json = response.get_json()
            self.assertEqual(response_json["error"], "Reset link has expired")

    def test_reset_password_missing_new_password(self):
        # Mock serializer.loads to return email
        with patch.object(self.app.serializer, "loads", return_value="test@example.com"):
            # Prepare data without new_password
            data = {}

            # Send POST request to /api/users/reset_password/<token>
            response = self.client.post(
                "/api/users/reset_password/test-token",
                data=json.dumps(data),
                content_type="application/json",
            )

            # Check response
            self.assertEqual(response.status_code, 400)
            response_json = response.get_json()
            self.assertEqual(response_json["error"], "New password is required")

    @patch("app.scan_users_by_attribute")
    def test_reset_password_user_not_found(self, mock_scan_users):
        # Mock serializer.loads to return email
        with patch.object(
            self.app.serializer, "loads", return_value="nonexistent@example.com"
        ):
            # Mock scan_users_by_attribute to return empty list
            mock_scan_users.return_value = []

            # Prepare data
            data = {
                "new_password": "NewPassword123"
            }

            # Send POST request to /api/users/reset_password/<token>
            response = self.client.post(
                "/api/users/reset_password/test-token",
                data=json.dumps(data),
                content_type="application/json",
            )

            # Check response
            self.assertEqual(response.status_code, 400)
            response_json = response.get_json()
            self.assertEqual(
                response_json["error"], "Invalid token or user does not exist"
            )

    @patch("app.update_user")
    def test_edit_user_success(self, mock_update_user):
        """
        Test that a user can successfully update allowed fields.
        """
        # Mock update_user to return True, indicating a successful update
        mock_update_user.return_value = True

        # Define the data to update
        update_data = {
            "username": "updateduser",
            "wishlist": ["item1", "item2"],
            "categories": ["category1", "category2"],
            "location": "Updated Location",
        }

        # Send POST request to /api/users/edit_user
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps(update_data),
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"message": "Updated user successfully"})

        # Verify that update_user was called with correct parameters
        mock_update_user.assert_called_once_with("testuser", update_data)

    def test_edit_user_no_data(self):
        """
        Test that the endpoint returns an error when no data is provided.
        """
        # Send POST request without any data
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=None,
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "No input data provided"})

    def test_edit_user_empty_data(self):
        """
        Test that the endpoint returns an error when empty JSON is provided.
        """
        # Send POST request with empty JSON
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps({}),
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "No input data provided"})

    @patch("app.update_user")
    def test_edit_user_restricted_fields(self, mock_update_user):
        """
        Test that attempting to modify restricted fields results in an error.
        """
        # Define the data with restricted fields
        update_data = {
            "email": "newemail@example.com",
            "password": "NewPassword123",
            "username": "newusername",
        }

        # Send POST request to /api/users/edit_user
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps(update_data),
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        error_message = response.get_json().get("error", "")

        # Define the expected restricted fields
        expected_fields = {"email", "password"}

        # Extract fields mentioned in the error message
        import re
        match = re.search(r"Modification of fields (.+) is not allowed\.", error_message)
        self.assertIsNotNone(match, "Error message format is incorrect.")
        fields_in_message = set(map(str.strip, match.group(1).split(',')))

        # Assert that all expected fields are present
        self.assertEqual(fields_in_message, expected_fields)

        # Verify that update_user was never called since request should be rejected
        mock_update_user.assert_not_called()


    @patch("app.update_user")
    def test_edit_user_partial_restricted_fields(self, mock_update_user):
        """
        Test that attempting to modify some restricted fields along with allowed fields results in an error.
        """
        # Define the data with both allowed and restricted fields
        update_data = {
            "username": "newusername",
            "email": "newemail@example.com",  # Restricted
            "location": "New Location",
        }

        # Send POST request to /api/users/edit_user
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps(update_data),
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn("Modification of fields email is not allowed.", response.get_json()["error"])

        # Verify that update_user was never called since request should be rejected
        mock_update_user.assert_not_called()

    @patch("app.update_user")
    def test_edit_user_update_failure(self, mock_update_user):
        """
        Test that the endpoint returns an error when the update_user function fails.
        """
        # Mock update_user to return False, indicating a failure
        mock_update_user.return_value = False

        # Define the data to update
        update_data = {
            "username": "updateduser",
            "wishlist": ["item1", "item2"],
            "categories": ["category1", "category2"],
            "location": "Updated Location",
        }

        # Send POST request to /api/users/edit_user
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps(update_data),
        )

        # Check the response
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Failed to update user"})

        # Verify that update_user was called with correct parameters
        mock_update_user.assert_called_once_with("testuser", update_data)

    @patch("app.update_user")
    def test_edit_user_exception_handling(self, mock_update_user):
        """
        Test that the endpoint handles exceptions raised by update_user gracefully.
        """
        # Mock update_user to raise an Exception
        mock_update_user.side_effect = Exception("DynamoDB Error")

        # Define the data to update
        update_data = {
            "username": "updateduser",
            "wishlist": ["item1", "item2"],
            "categories": ["category1", "category2"],
            "location": "Updated Location",
        }

        # Send POST request to /api/users/edit_user
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps(update_data),
        )

        # Check the response
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "An unexpected error occurred"})

        # Verify that update_user was called with correct parameters
        mock_update_user.assert_called_once_with("testuser", update_data)

    @patch("app.update_user")
    def test_edit_user_invalid_field_types(self, mock_update_user):
        """
        Test how the endpoint handles invalid data types for fields.
        For example, providing a string where a list is expected.
        """
        # Mock update_user to return True, assuming backend handles type validation
        # Since invalid data should prevent update_user from being called
        mock_update_user.return_value = True

        # Define the data with invalid types
        update_data = {
            "username": "updateduser",
            "wishlist": "should_be_a_list",  # Invalid type: should be a list
            "categories": ["category1", "category2"],
            "location": "Updated Location",
        }

        # Send POST request to /api/users/edit_user
        response = self.client.post(
            "/api/users/edit_user",
            headers=self.headers,
            data=json.dumps(update_data),
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid data types for fields: wishlist", response.get_json()["error"])

        # Verify that update_user was never called since validation failed
        mock_update_user.assert_not_called()


    @patch("app.scan_users_by_attribute")
    def test_get_public_user_info_success(self, mock_scan_users):
        # Mock user data to be returned by scan_users_by_attribute
        mock_user = {
            "id": "user123",
            "username": "testuser",
            "wishlist": ["item1", "item2"],
            "categories": ["Books", "Electronics"],
            "location": "New York",
            "password": "hashed_password",
            "email": "test@example.com",
            "email_verified": True
        }
        mock_scan_users.return_value = [mock_user]

        # Send GET request to /api/users/public_user_info with username parameter
        response = self.client.get(
            '/api/users/public_user_info',
            query_string={'username': 'testuser'},
            headers=self.headers
        )

        # Check the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Ensure only public fields are returned
        expected_fields = ['id', 'username', 'email', 'categories', 'location']
        self.assertTrue(all(field in data for field in expected_fields))
        self.assertNotIn('password', data)
        self.assertNotIn('wishlist', data)
        self.assertNotIn('email_verified', data)

        # Check that the returned data matches the mock user
        self.assertEqual(data['id'], mock_user['id'])
        self.assertEqual(data['username'], mock_user['username'])
        self.assertEqual(data['email'], mock_user['email'])
        self.assertEqual(data['categories'], mock_user['categories'])
        self.assertEqual(data['location'], mock_user['location'])

    def test_get_public_user_info_missing_username(self):
        # Send GET request without username parameter
        response = self.client.get(
            '/api/users/public_user_info',
            headers=self.headers
        )

        # Check the response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Username parameter is required')

    @patch("app.scan_users_by_attribute")
    def test_get_public_user_info_user_not_found(self, mock_scan_users):
        # Mock scan_users_by_attribute to return no users
        mock_scan_users.return_value = []

        # Send GET request with a username that does not exist
        response = self.client.get(
            '/api/users/public_user_info',
            query_string={'username': 'nonexistentuser'},
            headers=self.headers
        )

        # Check the response
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'User not found')

if __name__ == "__main__":
    unittest.main()