import base64
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
from langchain_google_genai import GoogleGenerativeAI
import logging
from bs4 import BeautifulSoup
from azure.storage.blob import BlobServiceClient, ContentSettings
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Azure Blob Storage configuration
STORAGE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
api_key = os.getenv("GOOGLE_API_KEY")
STATIC_WEBSITE_CONTAINER = "$web"  # Special container for static websites

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)



app = Flask(__name__)
CORS(app)


# In-memory store for user sessions
user_data = {}

# Folder where generated files will be stored
GENERATED_FOLDER = "generated_sites"

# Path to save uploaded images
UPLOAD_FOLDER = 'generated_websites'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(GENERATED_FOLDER):
    os.makedirs(GENERATED_FOLDER)

# Existing user website template path
USER_WEBSITE_TEMPLATE = os.path.join(app.root_path, 'templates', 'userwebsite.html')

# Phase 1 suggestions
website_types = ["Portfolio/CV", "Business", "Blog", "Webstore", "Landing Page"]
# Phase 2 color palette options
color_palettes = ["Dark-Mode", "Light-Mode "]
# Phase 3 functionality options
functionality_options = ["Red", "Green", "Blue", "Orange", "purple"]

@app.route('/')
def index():
    return "Hello, it’s THUTO here..."



from bs4 import BeautifulSoup  # Import BeautifulSoup for HTML parsing

@app.route('/chat', methods=['POST'])
def chat():
    logger.info("Received a POST request to /chat")
    user_input = request.json.get("inputs")
    
    # Extract image data list from the input
    image_data_list = user_input.get("businessImages", [])
    print("image_data_list: ", image_data_list)

    # Prepare the folder to save images in 'static/images'
    static_image_folder = os.path.join('static', 'images')
    os.makedirs(static_image_folder, exist_ok=True)  # Ensure the folder exists

    image_paths = []  # List to store relative paths of uploaded images

    # Loop through each image and save it in the 'static/images' folder
    for i, image_data in enumerate(image_data_list):
        img_data = base64.b64decode(image_data.split(',')[1])  # Decode base64 image data
        image_filename = f"uploaded_image_{i}.jpg"  # Unique filename for each image
        image_path = os.path.join(static_image_folder, image_filename)  # Full path to save the image
        
        # Save the image to the specified path
        with open(image_path, 'wb') as img_file:
            img_file.write(img_data)
        
        # Store the relative path to use in HTML
        image_paths.append(f"/static/images/{image_filename}")

    print("image_paths: ", image_paths)

    # Default user key setup
    default_user_key = "default_user"

    if default_user_key not in user_data:
        logger.debug(f"Initializing session for new user: {default_user_key}")
        user_data[default_user_key] = {"phase": 1, "responses": {}}
    else:
        logger.debug(f"User already exists. Current phase: {user_data[default_user_key]['phase']}")

    if user_input:
        logger.debug("user-data: %s", user_input)

        # Update user responses
        user_data[default_user_key]["responses"] = {
            "website_type": user_input.get("websiteType"),
            "theme": user_input.get("backgroundTheme"),
            "main_colour": user_input.get("mainColor"),
            "websiteName": user_input.get("websiteName"),
            "contactDetails": user_input.get("contactDetails"),
            "websiteContent": user_input.get("websiteContent"),
        }

        response_summary = user_data[default_user_key]["responses"]

        logger.info("========Generating values")
        api_key = os.getenv("GOOGLE_API_KEY")
        llm = GoogleGenerativeAI(model="gemini-1.5-pro-latest", api_key=api_key)
        
        descriptive_descrition_prompt = f"""
                                    You are a copywriter. Can you generate simple but 
                                    descriptive content based on this: {response_summary['websiteContent']}
                                """
        
        response_description = llm.invoke(descriptive_descrition_prompt)
        print("response_description", response_description)

        # Create prompt for generating website
        prompt = f"""Generate a modern website with HTML and CSS based on these details:
                     Structure: {response_summary['website_type']},
                     Content: {response_description},
                     Name: {response_summary['websiteName']},
                     Color: {response_summary['main_colour']},
                     Theme: {response_summary['theme']}.
                     - Include the following images: {image_paths}. Make sure to source 
                       the uploaded file in the in the following directory /static/images/.
                       If it containes multile images lease implement required UI.
                     - Prioritze using icons that will be suitable to the website, you can use from: https://fonts.google.com/icons
                     - Prioritze using font that will be suitable for teh website, you can use from: https://fonts.google.com/
                     - Prioritze using using styling from Bootstrap: https://getbootstrap.com/
                     - Ensure padding follows spacing of multiples of 48px.
                     - Add animations if possible to make it engaging.
                     - Prioritze the website can be viewed from mobile devices.
                  """

        response = llm.invoke(prompt)

        # Extract and clean the HTML content from response
        # generated_html = response.get('html', '') if isinstance(response, dict) else response
        # soup = BeautifulSoup(generated_html, 'html.parser')
        print('ntrition',response)


        # print('printing soup====',soup)
        final_html = extract_html_content(response)
        print('ntrition',final_html)

            # Save HTML content to a local file
        local_filename = "index.html"
        # save_html_to_file(generated_html, local_filename)
        save_html_to_file(final_html, local_filename)

        # Ensure the $web container exists
        create_web_container()

        # Upload the HTML file to Azure Blob Storage
        upload_html_to_blob(local_filename)

        # Get the URL for accessing the static website
        website_url = get_website_url()
   
        return jsonify({
            "message": "Your website has been generated! You can view it using the following link.",
            "link": "https://thutotesting.z19.web.core.windows.net/",
            "css_link": f"/static/css/{response_summary['websiteName']}.css",
            "phase": 5
        })
    else:
        logger.error("Invalid input format received.")
        return jsonify({"message": "Invalid input format. Please provide all required information."}), 400
    


def generate_website_html(response_summary):
    """Generate HTML content with embedded CSS based on the provided summary."""
    # Assuming the response_summary contains details needed for HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{response_summary['websiteName']}</title>
        <style>
            /* Your custom CSS based on the summary data */
            body {{ background-color: {response_summary['main_colour']}; }}
            /* Add more styles as needed */
        </style>
    </head>
    <body>
        <h1>{response_summary['websiteName']}</h1>
        <p>{response_summary['websiteContent']}</p>
        <p>Contact: {response_summary['contactDetails']}</p>
    </body>
    </html>
    """
    return html_content

def save_html_to_file(content, filename="index.html"):
    """Save HTML content to a local file."""
    with open(filename, "w") as file:
        file.write(content)
    print(f"File '{filename}' has been saved locally.")

def create_web_container():
    """Create the $web container if it doesn't exist for static website hosting."""
    try:
        container_client = blob_service_client.get_container_client(STATIC_WEBSITE_CONTAINER)
        if not container_client.exists():
            container_client.create_container()
            print(f"Container '{STATIC_WEBSITE_CONTAINER}' created for static website hosting.")
        else:
            print(f"Container '{STATIC_WEBSITE_CONTAINER}' already exists.")
    except Exception as e:
        print(f"Error creating or accessing the '{STATIC_WEBSITE_CONTAINER}' container: {e}")
        raise

def upload_html_to_blob(filename):
    """Upload the HTML file to the Azure Blob Storage $web container as 'index.html'."""
    blob_name = "index.html"  # Default filename for the static website
    try:
        container_client = blob_service_client.get_container_client(STATIC_WEBSITE_CONTAINER)
        with open(filename, "rb") as data:
            # Set the content type to 'text/html' to ensure the file is served correctly
            content_settings = ContentSettings(content_type="text/html")
            container_client.upload_blob(
                name=blob_name,
                data=data,
                overwrite=True,
                content_settings=content_settings
            )
        print(f"File '{filename}' successfully uploaded as '{blob_name}' with content type 'text/html' to the static website container.")
    except Exception as e:
        print(f"Failed to upload '{filename}' to the static website container: {e}")
        raise

def get_website_url():
    """Generate the URL for the static website."""
    account_name = blob_service_client.account_name
    website_url = f"https://{account_name}.z13.web.core.windows.net/"
    print(f"Static website URL: {website_url}")
    return website_url


def extract_html_content(content):
    """Extract only the HTML structure from the response text."""
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find the first <html> tag and its content
    html_tag = soup.find('html')
    if html_tag:
        return html_tag.prettify()
    
    # If no <html> tag is found, return cleaned content as-is
    return content.strip()

def generate_website_files(website_data):
    #     response_summary = {
    #     "website_type": user_input.get("websiteType"),
    #     "theme": user_input.get("backgroundTheme"),
    #     "main_colour": user_input.get("mainColor"),
    #     "websiteName": user_input.get("websiteName"),
    #     "contactDetails": user_input.get("contactDetails"),
    #     "websiteContent": user_input.get("websiteContent")
    # }

    print('start; ',website_data['website_type'])



    print("printing the value")
    api_key = os.getenv("GOOGLE_API_KEY")
    llm = GoogleGenerativeAI(model="gemini-1.5-pro-latest", api_key=api_key)

    # print("printing teh value, ",website_description)       
    prompt = f"""
    Generate a modern website with HTML and CSS:
    please elaborate on the description and content of the website,
    you can add elements such as header, cards etc.. to better visualize the website.
    please don't include any explanations.

    - Description: "{website_description}".

    Provide the output as a JSON object :
    'html': The HTML content of the webpage and the css.
    """

    # 1. 'html': The HTML content of the webpage.
    # 2. 'css': The CSS content for styling the webpage.

    response = llm.invoke(prompt)
    try:
        # print("Response: ", response)
        json_response = json.loads(response)
        return {
            "html": json_response.get("html"),
            "css": json_response.get("css")
        }
    except json.JSONDecodeError as e:
        print(f"Error: Unable to parse JSON response. Details: {str(e)}")
        return None

def populate_user_website(generated_files):
    # Populate the 'userwebsite.html' file with the generated HTML and CSS content
    html_content = generated_files.get("html", "<h1>Error generating HTML content</h1>")
    css_content = generated_files.get("css", "body { font-family: Arial; }")
    
    # Write HTML to userwebsite.html
    with open(USER_WEBSITE_TEMPLATE, 'w') as f:
        f.write(f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>User Generated Website</title>
    <style>{css_content}</style>
</head>
<body>
    {html_content}
</body>
</html>
        """)

@app.route('/view_website')
def view_website():
    # Render the user-generated website from the 'userwebsite.html' file
    return render_template('userwebsite.html')

def populate_user_website(generated_files):
    # Populate the 'userwebsite.html' file with the generated HTML and CSS content
    html_content = generated_files.get("html", "<h1>Error generating HTML content</h1>")
    css_content = generated_files.get("css", "body { font-family: Arial; }")
    
    # Write HTML to userwebsite.html
    with open(USER_WEBSITE_TEMPLATE, 'w') as f:
        f.write(f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>User Generated Website</title>
    <style>{css_content}</style>
</head>
<body>
    {html_content}
</body>
</html>
        """)

# Endpoint to handle chat updates and modify userwebsite.html
@app.route('/update_website', methods=['POST'])
def update_website():
    data = request.json
    instruction = data.get("instruction", "")

    # Example logic to modify HTML content based on instruction
    # You could expand this to recognize specific instructions
    with open(USER_WEBSITE_TEMPLATE, 'r+') as f:
        content = f.read()
        # Replace or append HTML based on the instruction
        if "change title" in instruction.lower():
            new_title = instruction.split("change title to ")[1]
            content = content.replace("<title>.*</title>", f"<title>{new_title}</title>")
        # Other modifications can be added here
        f.seek(0)
        f.write(content)
        f.truncate()

    return jsonify({"message": "Website updated successfully!"})


if __name__ == '__main__':
    logger.info("Starting the Flask application")
    app.run(debug=True)
