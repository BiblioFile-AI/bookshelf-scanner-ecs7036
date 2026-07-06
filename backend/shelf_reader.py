import os
import json
import time
import hashlib
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai


#API, cache, and genre set up.
load_dotenv()

#Retrieve gemini API key.
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    print("No API key found")

else:
    genai.configure(api_key=GOOGLE_API_KEY)

IMAGE_CACHE_FILE = "../data/image_extraction_cache.json"
GENRE_CACHE_FILE = "../data/genre_classification_cache.json"
RATE_LIMIT_DELAY = 1.0  

#10 official categories for the app:
OFFICIAL_GENRES = [
    "General & Contemporary Fiction", 
    "Romance", 
    "Mystery, Thriller & Crime", 
    "Science Fiction & Fantasy", 
    "Science, Tech & Nature", 
    "Young Adult", 
    "Children", 
    "Biography & Memoir", 
    "History & Politics", 
    "Self-Help & Lifestyle"
]



#JSON cache Functions:
def load_json_cache(filename):
    '''
    Input: filename - The path to the local JSON file to be read.
    Output: dict - The parsed data as a dictionary, or an empty dictionary {} if the file is missing or unreadable.

    Checks if the input file exists locally on the machine. If present, it attempts to open and decode its contents 
    from raw JSON into a dictionary. This serves to bypass redundant API lookups by reading historical 
    records. If the file doesn't exist yet or contains corrupted text, it returns an empty layout to prevent an error.
    '''

    
    #confirms file exists before attempting to open it. If not, returns an empty dictionary.
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                #Converts characters in file into a dict.
                return json.load(f)
            
            #Returns blank dict if the file is corrupted or unreadable.
            except json.JSONDecodeError:
                return {}
    
    return {}


def save_json_cache(data, filename):
    '''
    Input: data - The in-memory Python dictionary to be serialized and written to disk.
           filename - The destination file path on the hard drive.
    Output: None

    Takes an active in-memory Python dictionary and writes it onto the physical disk using a JSON layout with clean indentations. 
    Every time text is extracted or the LLM assigns a genre, this locks in those changes locally. Ensures that no data gains are 
    lost over the course of multiple runs.
    '''
    
    with open(filename, "w") as f:
        #write the live dictionary records onto the hard drive
        json.dump(data, f, indent=4)


def get_image_hash(image_path):
    """
    Input: image_path - The location of the shelf photo taken by the user.
    Output: str - A unique fingerprint for the image.

    Opens the file in binary read mode and feeds its raw bytes into an MD5 cryptographic hashing algorithm
    to generate a fingerprint for the image. This serves as an indexing key. By comparing this digital signature rather than checking 
    file names (which are subject to change), the application can check if the user has uploaded this exact photo before. 
    If matched, it can immediately pull the book list from the cache, saving significant processing time.
    """

    hasher = hashlib.md5()

    #opens image in raw binary mode so hash can be generated.
    with open(image_path, 'rb') as f:
        buffer = f.read()
        hasher.update(buffer)

    return hasher.hexdigest()


def generate_content_with_retry(model, contents, generation_config=None):
    '''
    Input: model (genai.GenerativeModel) - The Gemini LLM engine node.
           contents (list or str) - The data sent to the AI (e.g.text prompts and images).
           generation_config (dict) - Custom instructions for the AI. Used to enforce strict JSON output.
    Output: genai.types.GenerateContentResponse - The raw data returned by the Gemini service node.

    Calls Gemini using exponential back-off to manage network bottlenecks and rate limit exceptions. This loop intercepts 
    these problems by pausing the script execution, and automatically re-attempts the call at escalating wait intervals 
    (1, 2, 4, 8, and 16 seconds). This ensures that large shelves don't cause the program to fail.
    '''

    delays = [1, 2, 4, 8, 16]

    
    for delay in delays:
        try:
            #Checks if user has provided custom generation instructions.
            if generation_config:
                return model.generate_content(contents, generation_config=generation_config)
            
            else:
                return model.generate_content(contents)
        
        except Exception as e:
            err_msg = str(e)
            #If rate limit is hit or there is a quota message, pause and retry
            if "429" in err_msg or "quota" in err_msg.lower():
                time.sleep(delay)
            else:
                #If it's a different error, raise it.
                raise e
    
    
    #Final attempt before raising error.
    try:
        if generation_config:
            return model.generate_content(contents, generation_config=generation_config)
        else:
            return model.generate_content(contents)
    
    except Exception as e:
        raise Exception(f"API Call Failed: {str(e)}") from e



#Image to text extraction function
def extract_titles_and_authors(image_path):
    '''
    Input: image_path (str or Path) - The local file path to the bookshelf photo.
    Output: list of dicts - Author and title information for each book.

    Translates bookshelf image into text data. It first generates a digital MD5 fingerprint of the image file to check the image cache database. 
    If this exact photo has been processed previously, it bypasses the network entirely to load the historical text array. For new images, 
    it packages the file alongside structured prompt constraints and sends it to the 'gemini-2.5-flash' vision model, forcing a strict JSON 
    formatted response. Finally, it cleans any stray whitespace from the text and commits the book records to the cache so that downstream 
    metadata and genre classification modules receive clean data.
    '''
    
    #Checks if image file exists to prevent errors.
    if not os.path.exists(image_path):
        print(f"Target image file missing: {image_path}")
        return []

    
    #Getting the image hash to check if the photo has already been processed. Searches cache for match.
    img_cache = load_json_cache(IMAGE_CACHE_FILE)
    image_key = get_image_hash(image_path)
    
    
    if image_key in img_cache:
        print("\nThis photo was already scanned, loading from cache.")
        
        return img_cache[image_key]

    time.sleep(RATE_LIMIT_DELAY)

    
    vision_prompt = (
        "Look closely at this bookshelf image. Identify every unique book spine you can clearly read. "
        "Extract only the title and the author for each book. Return your output strictly as a JSON object "
        "using this exact structure:\n"
        '{"books": [{"title": "Example Title", "author": "Example Author"}]}\n'
        "Rules: Do not write conversational prose, and do not wrap the response in markdown code block ticks."
    )

    print("\nPassing image to Gemini API")
    
    try:
        img = Image.open(image_path)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        #executes API call.
        response = generate_content_with_retry(model, contents=[vision_prompt, img], generation_config={"response_mime_type": "application/json"})
        
        extracted_data = json.loads(response.text)
        books_list = extracted_data.get("books", [])

        #Clean the extracted text
        for book in books_list:
            book["title"] = str(book.get("title", "Unknown Title")).strip()
            book["author"] = str(book.get("author", "Unknown Author")).strip()

        #Save to image cache
        img_cache[image_key] = books_list
        save_json_cache(img_cache, IMAGE_CACHE_FILE)
        
        print(f"Found {len(books_list)} books on the shelf.")
        return books_list

    except Exception as e:
        print(f"Vision API failure: {e}")
        return []


def classify_books_batch(books):
    '''
    Input: books (list of dicts) - A collection of book objects extracted from either the vision or onboarding layers.
    Output: dict - A lookup index table mapping books to genres.

    Combines all uncached books into a prompt for a single batch LLM interaction. It filters through the incoming request array, 
    strips out items that already live inside the local JSON database, uses rigid instructions for the remaining books, and 
    retrieves their sorted genres in one go. This reduces total processing delay and respects rate limits.
    '''
    genre_cache = load_json_cache(GENRE_CACHE_FILE)
    
    uncached_books = []
    results = {}
    
    
    #Identify which books actually need API classification
    for book in books:
    
        #extracts the title and author from the book, creating a key for cache search.
        title = book.get("query_title") or book.get("title") or "Unknown Title"
        author = book.get("query_author") or book.get("authors") or book.get("author") or "Unknown Author"
        cache_key = f"{title} by {author}".lower().strip()
        
        #If the book is already in the cache, add it to the results. If not then queue it for classification.
        if cache_key in genre_cache:
            results[cache_key] = genre_cache[cache_key]
        else:
            uncached_books.append(book)
            
    if not uncached_books:
        return results

    print(f"Batch classifying {len(uncached_books)} new books")
    
    
    classification_prompt = (
        f"You are a strict book classification node. Your task is to assign a single genre string to each book in the list.\n"
        f"The genre MUST be chosen exactly from this official list: {OFFICIAL_GENRES}\n\n"
        "CRITICAL RULES FOR ACCURACY:\n"
        "1. DO NOT be lazy and default to 'General & Contemporary Fiction' for everything. Be highly specific!\n"
        "2. SCENARIO A: If the book object includes a 'categories' string from the API lookup, map it to the closest logical choice from our official list.\n"
        "3. SCENARIO B: If 'categories' is missing, empty, or 'None', analyze the Title and Author instead to determine the true genre.\n"
        "4. ANTI-HALLUCINATION RULE: If you do not recognize a book from your training memory, or if you are less than 90% confident, you MUST return 'Unknown'.\n"
        "5. You must return your output strictly as a JSON object with a single key 'classifications' containing a list of objects with 'title', 'author', and 'genre'.\n"
        "Example output structure:\n"
        '{"classifications": [{"title": "Example Title", "author": "Example Author", "genre": "History & Politics"}]}\n'
        "Do not write conversational prose, and do not wrap the response in markdown code blocks."
    )
    
    books_data_str = json.dumps(uncached_books, indent=2)
    full_prompt = f"{classification_prompt}\n\nBooks to classify:\n{books_data_str}"
    
    
    try:
        #Get classifications from the LLM
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = generate_content_with_retry(model, contents=full_prompt, generation_config={"response_mime_type": "application/json"})
        
        response_data = json.loads(response.text)
        classifications = response_data.get("classifications", [])
        

        for item in classifications:
            #Extract the title/ author/ genre from the output, default missing fields to "Unknown" to avoid errors.
            t_name = item.get("title", "Unknown Title")
            a_name = item.get("author", "Unknown Author")
            genre = item.get("genre", "Unknown")
            
            if genre not in OFFICIAL_GENRES:
                genre = "Unknown"
                
            
            cache_key = f"{t_name} by {a_name}".lower().strip()
            #saves genre to dictionary that gets written to disk.
            genre_cache[cache_key] = genre
            #saves genre to temporary dictionary for this function to output.
            results[cache_key] = genre
            
        #Fallback security check for anything the AI may have missed
        for book in uncached_books:

            t_name = book.get("query_title") or book.get("title") or "Unknown Title"
            a_name = book.get("query_author") or book.get("authors") or book.get("author") or "Unknown Author"
            cache_key = f"{t_name} by {a_name}".lower().strip()
            
            if cache_key not in results:
                genre_cache[cache_key] = "Unknown"
                results[cache_key] = "Unknown"
                
        save_json_cache(genre_cache, GENRE_CACHE_FILE)
        
    except Exception as e:
        
        print(f"Batch classification failure: {e}")
        
        for book in uncached_books:
            t_name = book.get("query_title") or book.get("title") or "Unknown Title"
            a_name = book.get("query_author") or book.get("authors") or book.get("author") or "Unknown Author"
            cache_key = f"{t_name} by {a_name}".lower().strip()
            results[cache_key] = "Unknown"
            
    return results


#Testing area
if __name__ == "__main__":
    test_image = "../data/mock_shelf_test.jpeg" 

    print("\n\nSTEP 1: EXTRACTION OF BOOK TITLES AND AUTHORS FROM IMAGE")
    scanned_books = extract_titles_and_authors(test_image)
    print(f"Data found on shelf:\n{json.dumps(scanned_books, indent=2)}")

  
    print("\n\nSTEP 2: BATCH GENRE CLASSIFICATION")
    
    if scanned_books:
        classifications = classify_books_batch(scanned_books)
        for book in scanned_books:
            key = f"{book['title']} by {book['author']}".lower().strip()
            genre = classifications.get(key, "Unknown")
            print(f"-> '{book['title']}' has been classified as: {genre}")
    else:
        print("No books found to classify.")