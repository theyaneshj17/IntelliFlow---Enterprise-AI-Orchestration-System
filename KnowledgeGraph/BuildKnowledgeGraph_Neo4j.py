import re
import csv
from collections import defaultdict
from neo4j import GraphDatabase
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords

# === CONFIG ===
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Cummins123"

INPUT_FILE = "C:/Users/theya/Downloads/Cummins/neo4j_triples.txt"
FAILED_OUTPUT_FILE = "C:/Users/theya/Downloads/Cummins/failed_triples1.txt"

# === INIT NLTK ===
nltk.download("wordnet")
nltk.download("stopwords")

lemmatizer = WordNetLemmatizer()
stopword_set = set(stopwords.words("english"))

# === UTILS ===
def normalize(text):
    return text.replace("'", "\\'")

def predicate_to_relation(pred):
    rel = pred.strip().upper().replace(" ", "_")
    rel = re.sub(r"[^A-Z0-9_]", "", rel)
    if not rel or not rel[0].isalpha():
        rel = "REL_" + rel
    return rel

def parse_csv_file(filename):
    """Parse CSV file containing triples"""
    triples = []
    with open(filename, 'r', encoding='utf-8') as file:
        # Try to detect if first line is header
        first_line = file.readline().strip()
        file.seek(0)  # Reset to beginning
        
        reader = csv.reader(file)
        
        # Skip header if it exists
        if 'doc_id' in first_line.lower() or 'subject' in first_line.lower():
            next(reader)  # Skip header row
            
        for row_num, row in enumerate(reader, 1):
            if len(row) >= 5:
                doc_id = row[0].strip()
                chunk_id = row[1].strip()
                subject = row[2].strip()
                predicate = row[3].strip()
                obj = row[4].strip()
                triples.append((doc_id, chunk_id, subject, predicate, obj))
            elif len(row) >= 3:
                # Handle case where only subject, predicate, object are provided
                subject = row[0].strip()
                predicate = row[1].strip()
                obj = row[2].strip()
                triples.append(("unknown", f"chunk_{row_num}", subject, predicate, obj))
            else:
                print(f"Warning: Row {row_num} has insufficient columns: {row}")
    
    return triples

def limit_predicate_length(predicate):
    return " ".join(predicate.split()[:5])

# === STANDARDIZATION ===
def normalize_text(text):
    words = re.findall(r'\b\w+\b', text.lower())
    filtered = [lemmatizer.lemmatize(w) for w in words if w not in stopword_set]
    return " ".join(filtered)

def standardize_entities(triples):
    print("Standardizing entity names across all triples...")
    if not triples:
        return triples

    print(f"Processing {len(triples)} triples...")

    # Collect all entities (subjects and objects)
    all_entities = set()
    for t in triples:
        all_entities.add(t[2].lower())  # subject
        all_entities.add(t[4].lower())  # object

    # Group similar entities
    entity_groups = defaultdict(list)
    for entity in sorted(all_entities, key=lambda x: (-len(x), x)):
        norm = normalize_text(entity)
        if norm:
            entity_groups[norm].append(entity)

    # Choose standard form for each group
    standardized_entities = {}
    for group, variants in entity_groups.items():
        if len(variants) == 1:
            standardized_entities[variants[0]] = variants[0]
        else:
            # Count frequency of each variant
            counts = defaultdict(int)
            for t in triples:
                for v in variants:
                    if t[2].lower() == v:
                        counts[v] += 1
                    if t[4].lower() == v:
                        counts[v] += 1
            # Choose most frequent variant, tie-break by shortest length
            std_form = sorted(variants, key=lambda x: (-counts[x], len(x)))[0]
            for v in variants:
                standardized_entities[v] = std_form

    # Apply standardization
    standardized_triples = []
    for t in triples:
        subj = standardized_entities.get(t[2].lower(), t[2])
        obj = standardized_entities.get(t[4].lower(), t[4])
        predicate = limit_predicate_length(t[3])
        standardized_triples.append((t[0], t[1], subj, predicate, obj))

    # Filter out self-referential triples
    filtered_triples = [t for t in standardized_triples if t[2].lower() != t[4].lower()]
    
    print(f"Standardized {len(all_entities)} entities into {len(set(standardized_entities.values()))} forms")
    print(f"Filtered out {len(standardized_triples) - len(filtered_triples)} self-referential triples")
    
    return filtered_triples

# === NEO4J UPLOAD ===
def upload_triples(driver, triples, keep_pubmed=True):
    failed = []
    successful = 0
    
    with driver.session() as session:
        for doc_id, chunk_id, subj, pred, obj in triples:
            try:
                subj = normalize(subj)
                obj = normalize(obj)
                rel = predicate_to_relation(pred)
                doc_id = doc_id.strip()
                chunk_id = chunk_id.strip()

                if keep_pubmed:
                    query = f"""
                    MERGE (s:Entity {{name: '{subj}'}})
                    MERGE (o:Entity {{name: '{obj}'}})
                    MERGE (s)-[r:{rel}]->(o)
                    SET r.source = '{doc_id}', r.chunk_id = '{chunk_id}'
                    """
                else:
                    query = f"""
                    MERGE (s:Entity {{name: '{subj}'}})
                    MERGE (o:Entity {{name: '{obj}'}})
                    MERGE (s)-[:{rel}]->(o)
                    """
                session.run(query)
                successful += 1
                
                if successful % 100 == 0:
                    print(f"Uploaded {successful} triples...")
                    
            except Exception as e:
                failed.append((doc_id, subj, pred, obj, str(e)))
                print(f"Failed to upload triple: ({subj}, {pred}, {obj}) - Error: {e}")

    print(f"✅ Successfully uploaded {successful} triples")
    
    if failed:
        with open(FAILED_OUTPUT_FILE, "w", encoding="utf-8") as f:
            for row in failed:
                f.write(f"{row}\n")
        print(f"❌ {len(failed)} triples failed. Logged to {FAILED_OUTPUT_FILE}")

# === MAIN ===
if __name__ == "__main__":
    print("Reading CSV file...")
    raw_triples = parse_csv_file(INPUT_FILE)
    
    print(f"Loaded {len(raw_triples)} raw triples")
    
    if raw_triples:
        # Show sample triples
        print("\nSample triples:")
        for i, triple in enumerate(raw_triples[:3]):
            print(f"  {i+1}: {triple}")
    
        standardized_triples = standardize_entities(raw_triples)

        print(f"\nConnecting to Neo4j at {NEO4J_URI}...")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        print(f"Uploading {len(standardized_triples)} standardized triples to Neo4j...")
        upload_triples(driver, standardized_triples, keep_pubmed=True)
        
        driver.close()
        print("✅ Process complete.")
    else:
        print("❌ No triples found in input file.")