from functools import wraps
from flask import redirect, session, render_template, request
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import re



def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function




def fetch_entity_image(entity_id):

    # Fetch entity details for the image
    entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
    entity_response = requests.get(entity_url)
    entity_data = entity_response.json()

    # Find the image (if it exists)
    claims = entity_data.get('entities', {}).get(entity_id, {}).get('claims', {})
    image_info = claims.get('P18')

    if image_info:
        image_file_name = image_info[0]['mainsnak']['datavalue']['value']
        return entity_id, f"https://commons.wikimedia.org/wiki/Special:FilePath/{image_file_name.replace(' ', '_')}"
    else:
        return entity_id,  "No image available for this entity."
    


def search_wikidata(query, limit=30):
    url = "https://www.wikidata.org/w/api.php"
    
    params = {
        'action': 'wbsearchentities',
        'format': 'json',
        'language': 'en',
        'search': query,
        'limit': limit
    }

    
    response = requests.get(url, params=params)
    
    data = response.json()




    results_list = []
    entity_ids = []

    # Collect basic entity info first
    for entity in data.get("search", []):
        result = {
            "label": entity.get("label"),
            "description": entity.get("description"),
            "entity_id": entity.get("id"),
            "wikidata_url": f"https://www.wikidata.org/wiki/{entity.get('id')}",
            "image_url": None
        }
        results_list.append(result)
        entity_ids.append(entity.get("id"))

    # Fetch images concurrently
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_entity_image, entity_id) for entity_id in entity_ids]
        # executes fetch_entity_image function with iterating through each entity_id as the requirement for each time it is ran
        image_map = {future.result()[0]: future.result()[1] for future in as_completed(futures)}
        # use as_completed when iterating through futures since they can have the future go through this iteration without having to wait for a separate future to complete making things quicker
        # since fetch_entity_image returns a tuple with two items (entity_id, image_url) image_map creates a dictionary with the id being the key and url being the value
        # the entity_id is in the [0] index since it is the first item and image_url is in the [1] index since it is the second item in the tuple 

        # Assign image URLs to results as futures complete
        for result in results_list:
            result["image_url"] = image_map.get(result["entity_id"])
            # iterates through each result/entity in results_list and connects the right image_url to the right entity_id ensuring each photo is placed with the right information 
    
    
    return results_list




def parse_quiz_output(response_text):
    # Split the response into individual questions using a pattern that finds the numbered questions.
    questions = re.split(r'\n(?=\d+\.)', response_text.strip())
    
    # Prepare an empty list to hold the parsed questions.
    parsed_questions = []
    
    # Process each question.
    for question_block in questions:
        # Split the question block into lines.
        lines = question_block.split('\n')
        
        # Extract the question itself.
        question = lines[0].strip()
        
        # Extract the answer options (assumed to be lines starting with a), b), etc.).
        options = [line.strip() for line in lines[1:5]]  # Assuming 4 options.
        
        # Extract the answer (format: "Answer: b)").
        answer_line = lines[5].strip()
        answer = answer_line.split("Answer:")[1].strip()
        
        # Extract the explanation (the line after the answer).
        explanation_line = lines[6].strip()
        explanation = explanation_line.split("Explanation:")[1].strip()
        
        # Set the media to None (since no media is present in this response).
        media = None
        
        # Build a dictionary for this question.
        question_dict = {
            'question': question,
            'options': options,
            'answer': answer,
            'explanation': explanation,
            'media': media
        }
        
        # Append the dictionary to the list of parsed questions.
        parsed_questions.append(question_dict)
    
    return parsed_questions


