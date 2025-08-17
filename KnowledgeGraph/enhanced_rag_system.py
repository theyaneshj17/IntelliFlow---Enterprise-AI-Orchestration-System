import anthropic
import ast
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer, util
import json
import re
from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter

# === CONFIG ===
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "******"
CLAUDE_API_KEY = "******"

# Reasoning parameters
MAX_HOPS = 3
MAX_PATHS_PER_ENTITY = 20
MAX_CONTEXT_TRIPLES = 50
MIN_PATH_SIMILARITY = 0.3

# === Init models ===
client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
embedder = SentenceTransformer("all-MiniLM-L6-v2")

class EnhancedMultiHopRAG:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
    def close(self):
        self.driver.close()
    
    # === STEP 1: Enhanced Entity Extraction ===
    def extract_entities_with_claude(self, question: str) -> List[str]:
        """Extract entities using Claude with research paper context"""
        prompt = f"""
Extract the most important entities from this question that would exist in a research paper knowledge graph.

Question: "{question}"

You must respond with ONLY a valid Python list format. Do not include any explanatory text, just the list.

Example format: ["entity1", "entity2", "entity3"]

Your response:"""
        
        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_output = response.content[0].text.strip()
            
            # Try to extract list using regex as backup
            list_match = re.search(r'\[([^\]]+)\]', raw_output)
            if list_match:
                list_str = '[' + list_match.group(1) + ']'
                try:
                    entities = ast.literal_eval(list_str)
                    return entities if isinstance(entities, list) else []
                except:
                    # Fallback: manual parsing
                    return self._parse_entities_manually(list_match.group(1))
            
            # If no list found, try direct evaluation
            entities = ast.literal_eval(raw_output)
            return entities if isinstance(entities, list) else []
            
        except Exception as e:
            print(f"Error extracting entities with Claude: {e}")
            # Fallback to rule-based extraction
            return self._extract_entities_fallback(question)
    
    def _parse_entities_manually(self, list_content: str) -> List[str]:
        """Manually parse entities from list content"""
        entities = []
        items = list_content.split(',')
        for item in items:
            # Clean up quotes and whitespace
            clean_item = item.strip().strip('"').strip("'").strip()
            if clean_item:
                entities.append(clean_item)
        return entities
    
    def _extract_entities_fallback(self, question: str) -> List[str]:
        """Fallback entity extraction using simple NLP techniques"""
        # Simple keyword-based extraction for technical terms
        question_lower = question.lower()
        entities = []
        
        # Common technical terms that might appear in research papers
        technical_patterns = [
            r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',  # Title case phrases
            r'\b(transformer|architecture|model|network|algorithm|method)\b',
            r'\b(machine translation|neural network|attention|encoder|decoder)\b',
            r'\b(performance|accuracy|evaluation|benchmark)\b'
        ]
        
        for pattern in technical_patterns:
            matches = re.findall(pattern, question, re.IGNORECASE)
            entities.extend(matches)
        
        # Remove duplicates and clean up
        unique_entities = list(set([e.strip() for e in entities if len(e.strip()) > 2]))
        return unique_entities[:8]  # Limit to 8 entities
    
    def find_similar_entities_in_kg(self, query_entities: List[str]) -> List[str]:
        """Find similar entities in the knowledge graph using fuzzy matching"""
        all_entities = set(query_entities)
        
        try:
            with self.driver.session() as session:
                for entity in query_entities:
                    # Direct fuzzy search in Neo4j
                    result = session.run("""
                        MATCH (n:Entity) 
                        WHERE toLower(n.name) CONTAINS toLower($entity)
                        RETURN n.name as name
                        LIMIT 10
                    """, entity=entity)
                    
                    for record in result:
                        all_entities.add(record['name'])
        except Exception as e:
            print(f"Error finding similar entities: {e}")
        
        return list(all_entities)
    
    # === STEP 2: Multi-Hop Path Discovery ===
    def discover_reasoning_paths(self, start_entities: List[str]) -> List[Dict]:
        """Discover multi-hop reasoning paths from start entities"""
        all_paths = []
        
        try:
            with self.driver.session() as session:
                for entity in start_entities:
                    # Find paths of different lengths (1 to MAX_HOPS)
                    query = f"""
                    MATCH path = (start:Entity)-[*1..{MAX_HOPS}]-(end:Entity)
                    WHERE start.name = $entity AND start <> end
                    WITH path, nodes(path) as path_nodes, relationships(path) as path_rels
                    RETURN [node in path_nodes | node.name] as node_sequence,
                           [rel in path_rels | type(rel)] as relation_sequence,
                           length(path) as path_length
                    LIMIT {MAX_PATHS_PER_ENTITY}
                    """
                    
                    result = session.run(query, entity=entity)
                    
                    for record in result:
                        node_seq = record['node_sequence']
                        rel_seq = record['relation_sequence']
                        
                        path_info = {
                            'start_entity': node_seq[0] if node_seq else entity,
                            'end_entity': node_seq[-1] if len(node_seq) > 1 else entity,
                            'node_sequence': node_seq,
                            'relation_sequence': rel_seq,
                            'path_length': record['path_length'],
                            'path_string': self._format_path(node_seq, rel_seq)
                        }
                        all_paths.append(path_info)
        except Exception as e:
            print(f"Error discovering reasoning paths: {e}")
        
        return all_paths
    
    def _format_path(self, nodes: List[str], relations: List[str]) -> str:
        """Format path as readable string"""
        if len(nodes) == 1:
            return nodes[0]
        
        path_parts = []
        for i in range(len(nodes) - 1):
            if i < len(relations):
                path_parts.append(f"{nodes[i]} --[{relations[i]}]--> {nodes[i+1]}")
            else:
                path_parts.append(f"{nodes[i]} --> {nodes[i+1]}")
        
        return " | ".join(path_parts)
    
    # === STEP 3: Path Ranking and Filtering ===
    def rank_paths_by_relevance(self, paths: List[Dict], question: str) -> List[Tuple[Dict, float]]:
        """Rank paths by semantic relevance to the question"""
        if not paths:
            return []
        
        try:
            question_embedding = embedder.encode(question)
            scored_paths = []
            
            for path in paths:
                # Create path representation for scoring
                path_text = f"{path['path_string']} {' '.join(path['node_sequence'])}"
                path_embedding = embedder.encode(path_text)
                
                # Calculate similarity
                similarity = util.cos_sim(question_embedding, path_embedding).item()
                
                # Boost score for shorter paths (more direct relationships)
                length_penalty = 1.0 / (path['path_length'] + 1)
                final_score = similarity * (0.7 + 0.3 * length_penalty)
                
                if final_score >= MIN_PATH_SIMILARITY:
                    scored_paths.append((path, final_score))
            
            # Sort by score descending
            return sorted(scored_paths, key=lambda x: x[1], reverse=True)
        except Exception as e:
            print(f"Error ranking paths: {e}")
            return []
    
    # === STEP 4: Context Assembly ===
    def assemble_context_from_paths(self, ranked_paths: List[Tuple[Dict, float]], 
                                   question: str) -> List[str]:
        """Assemble context triples from top-ranked paths"""
        context_triples = []
        seen_triples = set()
        entity_coverage = defaultdict(int)
        
        try:
            # Extract individual triples from paths
            for path, score in ranked_paths[:MAX_CONTEXT_TRIPLES]:
                nodes = path['node_sequence']
                relations = path['relation_sequence']
                
                # Extract triples from this path
                for i in range(len(nodes) - 1):
                    if i < len(relations):
                        subject = nodes[i]
                        predicate = relations[i]
                        obj = nodes[i + 1]
                        
                        triple_key = (subject.lower(), predicate.lower(), obj.lower())
                        if triple_key not in seen_triples:
                            seen_triples.add(triple_key)
                            
                            # Format triple with score info
                            triple_str = f"({subject}) --[{predicate}]--> ({obj})"
                            context_triples.append(triple_str)
                            
                            # Track entity coverage
                            entity_coverage[subject] += 1
                            entity_coverage[obj] += 1
            
            # Add direct single-hop triples for high-frequency entities
            self._add_direct_triples(context_triples, entity_coverage, question)
        except Exception as e:
            print(f"Error assembling context: {e}")
        
        return context_triples[:MAX_CONTEXT_TRIPLES]
    
    def _add_direct_triples(self, context_triples: List[str], 
                           entity_coverage: Dict[str, int], question: str):
        """Add direct triples for important entities"""
        try:
            # Find top entities by frequency
            top_entities = [entity for entity, count in 
                           Counter(entity_coverage).most_common(5)]
            
            with self.driver.session() as session:
                for entity in top_entities:
                    # Get direct relationships
                    query = """
                    MATCH (s:Entity {name: $entity})-[r]->(o:Entity)
                    RETURN s.name as subject, type(r) as relation, o.name as object
                    UNION
                    MATCH (s:Entity)-[r]->(o:Entity {name: $entity})
                    RETURN s.name as subject, type(r) as relation, o.name as object
                    LIMIT 5
                    """
                    
                    result = session.run(query, entity=entity)
                    
                    for record in result:
                        triple_str = f"({record['subject']}) --[{record['relation']}]--> ({record['object']})"
                        if triple_str not in context_triples:
                            context_triples.append(triple_str)
        except Exception as e:
            print(f"Error adding direct triples: {e}")
    
    # === STEP 5: Claude Answer Generation ===
    def generate_answer_with_reasoning(self, context_triples: List[str], 
                                     reasoning_paths: List[Tuple[Dict, float]], 
                                     question: str) -> str:
        """Generate answer using Claude with multi-hop reasoning context"""
        
        try:
            # Format reasoning paths for Claude
            top_paths = reasoning_paths[:10]  # Top 10 paths
            path_descriptions = []
            for i, (path, score) in enumerate(top_paths, 1):
                path_desc = f"Path {i} (relevance: {score:.3f}): {path['path_string']}"
                path_descriptions.append(path_desc)
            
            prompt = f"""
You are an expert research assistant analyzing a knowledge graph extracted from research papers. Use the provided reasoning paths and knowledge triples to answer the question comprehensively.

MULTI-HOP REASONING PATHS:
{chr(10).join(path_descriptions) if path_descriptions else "No reasoning paths found."}

KNOWLEDGE GRAPH CONTEXT:
{chr(10).join(context_triples) if context_triples else "No context triples available."}

QUESTION: {question}

INSTRUCTIONS:
1. Analyze the reasoning paths to understand multi-step relationships
2. Use the knowledge triples as supporting evidence
3. Explain your reasoning process and cite specific relationships
4. If multiple paths lead to different conclusions, discuss them
5. Indicate confidence level based on evidence strength
6. If no relevant paths or context are available, provide a general answer based on your knowledge

ANSWER:
"""
            
            response = client.messages.create(
                model="claude-3-haiku-20240307",  # Using Sonnet for better reasoning
                max_tokens=4000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error generating answer: {e}")
            return f"Error generating answer: {str(e)}"
    
    # === MAIN QUERY FUNCTION ===
    def query(self, question: str) -> Dict:
        """Main query function that orchestrates the multi-hop RAG process"""
        print(f"\n🔍 Processing question: {question}")
        
        try:
            # Step 1: Extract entities
            print("📋 Extracting entities...")
            query_entities = self.extract_entities_with_claude(question)
            extended_entities = self.find_similar_entities_in_kg(query_entities)
            print(f"   Found entities: {extended_entities}")
            
            # Step 2: Discover reasoning paths
            print("🕸️ Discovering reasoning paths...")
            reasoning_paths = self.discover_reasoning_paths(extended_entities)
            print(f"   Found {len(reasoning_paths)} reasoning paths")
            
            # Step 3: Rank paths by relevance
            print("📊 Ranking paths by relevance...")
            ranked_paths = self.rank_paths_by_relevance(reasoning_paths, question)
            print(f"   {len(ranked_paths)} relevant paths identified")
            
            # Step 4: Assemble context
            print("🔗 Assembling context...")
            context_triples = self.assemble_context_from_paths(ranked_paths, question)
            print(f"   {len(context_triples)} context triples selected")
            
            # Step 5: Generate answer
            print("🧠 Generating answer...")
            answer = self.generate_answer_with_reasoning(context_triples, ranked_paths, question)
            
            # Return comprehensive result
            return {
                'question': question,
                'answer': answer,
                'entities_used': extended_entities,
                'reasoning_paths_count': len(ranked_paths),
                'context_triples_count': len(context_triples),
                'top_reasoning_paths': [path for path, score in ranked_paths[:5]],
                'context_triples': context_triples
            }
        except Exception as e:
            print(f"Error in query processing: {e}")
            return {
                'question': question,
                'answer': f"Error processing query: {str(e)}",
                'entities_used': [],
                'reasoning_paths_count': 0,
                'context_triples_count': 0,
                'top_reasoning_paths': [],
                'context_triples': []
            }

# === MAIN EXECUTION ===
def main():
    rag_system = EnhancedMultiHopRAG()
    
    try:
        while True:
            question = input("\n💭 Enter your research question (or 'quit' to exit): ")
            if question.lower() == 'quit':
                break
                
            result = rag_system.query(question)
            
            print(f"\n✅ ANSWER:")
            print(result['answer'])
            
            print(f"\n📈 REASONING SUMMARY:")
            print(f"   - Entities analyzed: {len(result['entities_used'])}")
            print(f"   - Reasoning paths found: {result['reasoning_paths_count']}")
            print(f"   - Context triples used: {result['context_triples_count']}")
            
            # Show top reasoning paths
            if result['top_reasoning_paths']:
                print(f"\n🔍 TOP REASONING PATHS:")
                for i, path in enumerate(result['top_reasoning_paths'][:3], 1):
                    print(f"   {i}. {path['path_string']}")
    
    finally:
        rag_system.close()

if __name__ == "__main__":
    main()