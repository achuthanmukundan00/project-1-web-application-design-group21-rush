import os
import pytest
import boto3
from app import app
from dotenv import load_dotenv
from datetime import datetime
import uuid
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

# set these in your own environment when testing (just match the docker-compose.yml file)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_LISTINGS_BUCKET_NAME = os.getenv('AWS_S3_LISTINGS_BUCKET_NAME')
AWS_DB_LISTINGS_TABLE_NAME = os.getenv('AWS_DB_LISTINGS_TABLE_NAME')
AWS_S3_REGION = os.getenv('AWS_S3_REGION')

@pytest.fixture
def client():
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client

def test_real_listings_s3_upload(client):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION
    )

    image_path = 'listings_service/test_image.jpg'
    with open(image_path, 'rb') as img_file:
        data = {
            'file': (img_file, 'test_image.jpg')
        }

        # upload test_image.jpg to the listings bucket
        response = client.post('/upload', data=data, content_type='multipart/form-data')

        assert response.status_code == 200
        response_data = response.get_json()
        assert 'file_url' in response_data

        response = s3_client.list_objects_v2(Bucket=AWS_S3_LISTINGS_BUCKET_NAME)
        file_exists = any(obj['Key'] == 'listings/test_image.jpg' for obj in response.get('Contents', []))
        assert file_exists, "Uploaded file not found in S3 bucket"

    # delete the test image from the listings bucket
    s3_client.delete_object(Bucket=AWS_S3_LISTINGS_BUCKET_NAME, Key='listings/test_image.jpg')

def test_real_listings_dynamodb_and_s3_upload(client):
    # Generate a unique ID for the test listing
    listing_id = str(uuid.uuid4())
    image_files = ['listings_service/test_image.jpg', 'listings_service/test_image2.jpg']
    image_filenames = [f"{listing_id}/test_image.jpg", f"{listing_id}/test_image2.jpg"]  # Expected filenames in S3

    # Prepare form data
    data = {
        'id': listing_id,
        'title': 'New Test Listing Title',
        'description': 'This is a description for a test listing.',
        'price': '20',
        'location': 'St. George',
        'condition': 'Used',
        'category': 'Electronics',
        'datePosted': datetime.now().isoformat(),
        'sellerId': 'test_seller_id',
        'sellerName': 'Test Seller'
    }

    with open(image_files[0], 'rb') as img1, open(image_files[1], 'rb') as img2:
        data['file'] = [
            (img1, 'test_image.jpg'),
            (img2, 'test_image2.jpg')
        ]

        # Send POST request to the Flask endpoint
        response = client.post('/api/listings/create-listing', data=data, content_type='multipart/form-data')
        assert response.status_code == 200
        response_data = response.get_json()
        assert 'message' in response_data and response_data['message'] == 'Listing created successfully'

    # initialize DynamoDB client
    dynamodb_client = boto3.client(
        'dynamodb',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION
    )
    
    # make sure the data ended up in the dynamoDB listings table
    response = dynamodb_client.get_item(
        TableName=AWS_DB_LISTINGS_TABLE_NAME,
        Key={'id': {'S': listing_id}}
    )
    item = response.get('Item')
    assert item is not None, "Item not found in DynamoDB"
    assert item['title']['S'] == 'New Test Listing Title'
    assert item['description']['S'] == 'This is a description for a test listing.'
    assert item['price']['N'] == '20'

    expected_image_urls = [
        f"https://{AWS_S3_LISTINGS_BUCKET_NAME}.s3.amazonaws.com/listings/{filename}"
        for filename in image_filenames
    ]

    assert set(item['images']['SS']) == set(expected_image_urls), f"Image URLs do not match. Expected: {expected_image_urls}, Got: {item['images']['SS']}"


    # initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION
    )

    # make sure images were uploaded to listings S3 bucket
    for filename in image_filenames:
        try:
            s3_client.head_object(Bucket=AWS_S3_LISTINGS_BUCKET_NAME, Key=f"listings/{filename}")
        except s3_client.exceptions.ClientError:
            assert False, f"Image {filename} not found in S3 bucket"

def test_delete_specific_listing(client):
    # Specify the listing ID you want to delete
    listing_id = 'ca839416-2055-44b2-be16-50b3d327b409'  # Replace with the actual listing ID

    # Step 1: Send DELETE request to remove the listing
    delete_response = client.delete(f'/api/listings/delete/{listing_id}')
    assert delete_response.status_code == 200
    delete_response_data = delete_response.get_json()
    assert 'message' in delete_response_data and delete_response_data['message'] == f'Listing with id {listing_id} deleted successfully'

    # Step 2: Verify that the listing no longer exists in DynamoDB
    dynamodb_client = boto3.client(
        'dynamodb',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION
    )
    
    # Try to retrieve the item from DynamoDB
    response = dynamodb_client.get_item(
        TableName=AWS_DB_LISTINGS_TABLE_NAME,
        Key={'id': {'S': listing_id}}
    )
    item = response.get('Item')
    assert item is None, f"Listing with id {listing_id} was not deleted from DynamoDB"

def test_get_all_listings(client):
    # send GET request to retrieve all listings
    response = client.get('/api/listings/all')

    # check response status code
    assert response.status_code == 200, "Expected status code 200, but got {response.status_code}"

    # parse response JSON
    response_data = response.get_json()
    listings = response_data.get('listings', [])

    # verify that 33 are returned (that's just what existed at the time of writing this code)
    assert len(listings) == 33, f"Expected 33 listings, but got {len(listings)}"

    listing_ids = [listing['id'] for listing in listings]
    logging.info(f"Retrieved listing IDs: {listing_ids}")
    logging.info(f"Retrieved listings: {listings}")

def test_get_listings_by_seller_id(client):
    expected_listing_ids = ['testanotherid', 'testsearchlisting']

    response = client.get(f'/api/listings/user/Niv')
    assert response.status_code == 200

    response_data = response.get_json()
    listings = response_data.get('listings', [])

    # check that 2 are retrieved
    assert len(listings) == 2, f"Expected 2 listings for seller ID, got {len(listings)}"

    # check that it's the exact 2 we're expecting
    retrieved_listing_ids = [listing['id'] for listing in listings]
    logging.info(f"Retrieved listing IDs: {retrieved_listing_ids}")
    
    assert set(retrieved_listing_ids) == set(expected_listing_ids), f"Expected listing IDs {expected_listing_ids}, got {retrieved_listing_ids}"

def test_get_listings_by_category(client):
    expected_listing_ids = ['furniture2', 'furnitureitemid']

    response = client.get(f'/api/listings/category/furniture')
    assert response.status_code == 200

    response_data = response.get_json()
    listings = response_data.get('listings', [])

    # check that 2 are retrieved
    assert len(listings) == 2, f"Expected 2 listings for seller ID, got {len(listings)}"

    # check that it's the exact 2 we're expecting
    retrieved_listing_ids = [listing['id'] for listing in listings]
    logging.info(f"Retrieved listing IDs: {retrieved_listing_ids}")
    
    assert set(retrieved_listing_ids) == set(expected_listing_ids), f"Expected listing IDs {expected_listing_ids}, got {retrieved_listing_ids}"

def test_edit_specific_listing_with_image(client):
    # going to try editing this specific listing
    listing_id = '66583262-1b66-4601-afc3-5f283421c8f0'

    # update the category 
    updated_data = {
        'category': 'furniture'
    }

    # open the test image file in binary mode
    image_path = os.path.join(os.path.dirname(__file__), 'furniture_image.jpg')
    with open(image_path, 'rb') as img_file:
        # add the image file to the data being sent in the request
        data = {
            'category': 'furniture',
            'file': (img_file, image_path)  # Add the image as a file
        }

        # send PUT request to edit the listing, including the image
        edit_response = client.put(f'/api/listings/edit/{listing_id}', data=data, content_type='multipart/form-data')
        assert edit_response.status_code == 200
        edit_response_data = edit_response.get_json()
        assert 'message' in edit_response_data and edit_response_data['message'] == 'Listing updated successfully'

    # initialize ddb client to verify update
    dynamodb_client = boto3.client(
        'dynamodb',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION
    )
    
    # retrieve the updated item from DynamoDB
    response = dynamodb_client.get_item(
        TableName=AWS_DB_LISTINGS_TABLE_NAME,
        Key={'id': {'S': listing_id}}
    )
    item = response.get('Item')
    assert item is not None, f"Listing with id {listing_id} was not found in DynamoDB after edit"
    assert item['category']['S'] == 'furniture', f"Expected category to be 'furniture', but got {item['category']['S']}"

    # verify that new image was added to S3 bucket
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_S3_REGION
    )

    # check if it's in the right location
    expected_image_key = f"listings/{listing_id}/test_image.jpg"
    try:
        s3_client.head_object(Bucket=AWS_S3_LISTINGS_BUCKET_NAME, Key=expected_image_key)
    except s3_client.exceptions.ClientError:
        assert False, f"Image {expected_image_key} not found in S3 bucket"
