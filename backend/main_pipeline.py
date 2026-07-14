import pandas as pd
import shelf_reader
import metadata_lookup

def prep_recommendation_data(scanned_books_input, user_profile_input):
    '''
    Input: scanned_books_input (list of dicts/ tuples) - The collection of book titles and authors.
           user_profile_input (list of dicts/tuples/str) - The books the user says they enjoyed,
               or an empty list if they have no saved profile yet.
    Output: clean_df (pd.DataFrame) - A polished table containing metadata for the scanned books.
            feature_vectors_df (pd.DataFrame) - A matrix containing normalized genre indices and z-scores
                for the scanned books.
            profile_vectors (np.ndarray or None) - The same kind of vectors for the user's saved profile,
                built with the SAME fitted scaler as feature_vectors_df so the two are directly comparable.
                None when user_profile_input is empty (no saved profile to rank against yet).

    Manages the flow of data from raw input to finalized numerical features. It first deploys an input normalization layer to
    safely handle data format discrepancies (translating camera dictionaries into catalog tuples and vice-versa). It then runs batch
    LLM genre classification, querying external databases with fallback coverage, and addresses missing data. Finally, it uses the user's
    profile of liked books to normalise and scale the features, converting the bookshelf information into matrices.
    '''
    print("STARTING BOOKSHELF PIPELINE")

    #Standardise inputs between modules
    if isinstance(scanned_books_input[0], dict):
        scanned_books_list = scanned_books_input
        tuple_books_list = [(b.get("title"), b.get("author")) for b in scanned_books_input]

    else:
        tuple_books_list = scanned_books_input
        scanned_books_list = [{"title": t, "author": a} for t, a in scanned_books_input]

    #A real (non-empty) profile gets real vectors back; an empty one only
    #needs a placeholder so the scaler below still has something to fit on.
    has_real_profile = bool(user_profile_input)
    profile_source = user_profile_input if has_real_profile else [{"title": "Unknown", "authors": "Unknown"}]

    #Genre classification with shelf_reader.py
    print("\nRunning Batch LLM Genre Classification...")
    genre_results_dict = shelf_reader.classify_books_batch(scanned_books_list)

    #Metadata lookup for the scanned shelf books
    print("\nFetching Catalog Metadata for Scanned Shelf...")
    raw_df = metadata_lookup.build_metadata_table(tuple_books_list, api_keys=metadata_lookup.API_KEYS)
    full_df = metadata_lookup.apply_fallback(raw_df)
    clean_df, dropped_count = metadata_lookup.apply_missing_data_policy(full_df)

    #Fetch metadata for the user profile books to build the baseline
    #(this is the ONLY place profile metadata is fetched - it used to also
    #be rebuilt from scratch in app.py, which doubled the Google Books/pandas
    #work on every single scan).
    print("\nFetching Catalog Metadata for User Profile Baseline...")
    #Check if the profile is a list of tuples/dicts, or just flat title strings
    if isinstance(profile_source[0], dict):
        profile_tuples = [(b.get("title"), b.get("author") or b.get("authors")) for b in profile_source]

    elif isinstance(profile_source[0], tuple):
        profile_tuples = profile_source

    else:
        #Fallback if user only passes plain text title strings
        profile_tuples = [(title, "Unknown") for title in profile_source]

    raw_profile_df = metadata_lookup.build_metadata_table(profile_tuples, api_keys=metadata_lookup.API_KEYS)
    full_profile_df = metadata_lookup.apply_fallback(raw_profile_df)
    profile_df, _ = metadata_lookup.apply_missing_data_policy(full_profile_df)



    print("\nCreating Final Feature Vectors...")

    #Reconstruct the combined key ("title by author") to map genres
    final_genre_labels = []
    for idx, row in clean_df.iterrows():
        lookup_key = f"{row['query_title']} by {row['query_author']}".lower().strip()

        #Look up the AI-classified genre, using "General & Contemporary Fiction" as a safety net if the key is missing
        final_genre_labels.append(genre_results_dict.get(lookup_key, "General & Contemporary Fiction"))

    #Carry the classified genre back onto the table so the API response
    #can show it instead of Google Books' raw, uncontrolled category text
    clean_df = clean_df.copy()
    clean_df["genre_label"] = final_genre_labels


    #Extract unique authors from the profile dataset
    profile_authors = list(profile_df["authors"].dropna().unique())

    #Calculate the average and mathematical baseline from the profile
    scaler = metadata_lookup.fit_profile_scaler(profile_df)


    #Build the final feature vectors for all books in the scanned shelf
    feature_vectors_df = metadata_lookup.build_feature_vectors(df=clean_df, genre_labels=final_genre_labels, profile_authors=profile_authors, scaler=scaler)

    #Build the profile's own vectors with the SAME scaler, so scanned vs.
    #profile vectors are on the same normalised scale for KNN to compare.
    profile_vectors = None
    if has_real_profile and not profile_df.empty:
        books_for_genre = [
            {"title": row["query_title"], "authors": row.get("query_author", "")}
            for _, row in profile_df.iterrows()
        ]
        profile_genre_results = shelf_reader.classify_books_batch(books_for_genre)
        profile_genre_labels = [
            profile_genre_results.get(
                f"{row['query_title']} by {row['query_author']}".lower().strip(),
                "General & Contemporary Fiction"
            )
            for _, row in profile_df.iterrows()
        ]
        profile_vectors = metadata_lookup.build_feature_vectors(
            df=profile_df,
            genre_labels=profile_genre_labels,
            profile_authors=profile_authors,
            scaler=scaler,
        ).to_numpy()

    print("\nPIPELINE SUCCESSFUL")
    return clean_df, feature_vectors_df, profile_vectors



#Test the pipeline with a sample shelf and user profile
if __name__ == "__main__":
    #Test 1 using simulated scanned shelf
    sample_shelf = [
        ("Red Rising", "Pierce Brown"),         
        ("The Secret History", "Donna Tartt"),  
        ("Sapiens", "Yuval Noah Harari"),       
        ("The Hobbit", "J.R.R. Tolkien"),       
        ("Dune", "Frank Herbert")               
    ]
    
    sample_user_profile = [
        ("The Secret History", "Donna Tartt"),
        ("The Hobbit", "J.R.R. Tolkien"),
        ("Dune", "Frank Herbert")
    ]
    
    metadata_results, final_vectors, profile_vectors = prep_recommendation_data(sample_shelf, sample_user_profile)
    

    print("\nFinal feature vectors for test 1:")
    print(final_vectors)


    #Test 2 using image extraction of unfamiliar books
    my_image_path = "../data/mock_shelf_test.jpeg"
    scanned_dicts = shelf_reader.extract_titles_and_authors(my_image_path)



    if not scanned_dicts:
        print("\nVision Test Failed")
    else:
        print(f"\nSuccessfully extracted {len(scanned_dicts)} books from image.")

        print("Feeding visual data into the feature extraction engine...")
        
        scan_metadata_results, scan_final_vectors, scan_profile_vectors = prep_recommendation_data(scanned_dicts, sample_user_profile)
        
        print("\nFinal feature vectors for test 2:")
        print(scan_final_vectors)