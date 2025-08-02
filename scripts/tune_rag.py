#!/usr/bin/env python3

import os
import sys
import yaml
import json
import itertools
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config_loader import load_config
from retrieval.unified_rag import UnifiedRAG
import argparse


class RAGTuner:
    def __init__(self, base_config_path: str = None):
        self.base_config = load_config(base_config_path or "config.yaml")
        self.test_queries = []
        self.results = []
    
    def load_test_queries(self, queries_path: str):
        if queries_path.endswith('.jsonl'):
            with open(queries_path, 'r') as f:
                self.test_queries = [json.loads(line) for line in f]
        elif queries_path.endswith('.yaml') or queries_path.endswith('.yml'):
            with open(queries_path, 'r') as f:
                data = yaml.safe_load(f)
                self.test_queries = data.get('queries', [])
        else:
            raise ValueError("Unsupported file format. Use .jsonl or .yaml")
    
    def generate_configs(self) -> List[Dict[str, Any]]:
        grid_params = {
            'chunker.target_tokens': [512, 768, 1024],
            'chunker.overlap_ratio': [0.10, 0.15, 0.20],
            'retrieval.k_dense': [20, 40, 60],
            'retrieval.k_sparse': [20, 40, 60],
            'retrieval.rrf_k': [40, 60, 80]
        }
        
        configs = []
        param_names = list(grid_params.keys())
        param_values = list(grid_params.values())
        
        for combination in itertools.product(*param_values):
            config = self.base_config.copy()
            
            for param_name, value in zip(param_names, combination):
                keys = param_name.split('.')
                current = config
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[keys[-1]] = value
            
            configs.append(config)
        
        return configs
    
    def evaluate_config(self, config: Dict[str, Any]) -> Dict[str, float]:
        rag_system = UnifiedRAG()
        rag_system.config = config
        
        correct_answers = 0
        total_queries = len(self.test_queries)
        citation_accuracy = 0
        relevance_scores = []
        
        for query_data in self.test_queries:
            query = query_data.get('question', '')
            expected_contains = query_data.get('must_contain', [])
            expected_citations = query_data.get('must_cite_substring', [])
            
            try:
                answer, chunks = rag_system.answer_question(
                    query,
                    student_program=query_data.get('major'),
                    student_year=query_data.get('year'),
                    use_streaming=False
                )
                
                if isinstance(answer, str):
                    answer_text = answer
                else:
                    answer_text = str(answer)
                
                contains_score = 0
                for expected in expected_contains:
                    if expected.lower() in answer_text.lower():
                        contains_score += 1
                
                if expected_contains:
                    correct_answers += contains_score / len(expected_contains)
                
                citation_score = 0
                for expected_cite in expected_citations:
                    for chunk in chunks:
                        chunk_text = chunk.get('text', '')
                        if expected_cite.lower() in chunk_text.lower():
                            citation_score += 1
                            break
                
                if expected_citations:
                    citation_accuracy += citation_score / len(expected_citations)
                
                relevance_scores.append(self._calculate_relevance(query, chunks))
                
            except Exception as e:
                print(f"Error evaluating query '{query}': {e}")
                continue
        
        accuracy = correct_answers / total_queries if total_queries > 0 else 0
        citation_acc = citation_accuracy / total_queries if total_queries > 0 else 0
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        composite_score = (accuracy * 0.4) + (citation_acc * 0.3) + (avg_relevance * 0.3)
        
        return {
            'accuracy': accuracy,
            'citation_accuracy': citation_acc,
            'relevance': avg_relevance,
            'composite_score': composite_score
        }
    
    def _calculate_relevance(self, query: str, chunks: List[Dict]) -> float:
        if not chunks:
            return 0.0
        
        query_words = set(query.lower().split())
        relevance_scores = []
        
        for chunk in chunks[:5]:
            chunk_text = chunk.get('text', '').lower()
            chunk_words = set(chunk_text.split())
            
            if query_words:
                overlap = len(query_words.intersection(chunk_words))
                relevance = overlap / len(query_words)
                relevance_scores.append(relevance)
        
        return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    def tune(self, queries_path: str, output_dir: str = "configs/auto_tuned"):
        self.load_test_queries(queries_path)
        configs = self.generate_configs()
        
        print(f"Evaluating {len(configs)} configurations...")
        
        best_config = None
        best_score = -1
        
        for i, config in enumerate(configs):
            print(f"Evaluating config {i+1}/{len(configs)}")
            
            try:
                metrics = self.evaluate_config(config)
                
                result = {
                    'config_id': i,
                    'config': config,
                    'metrics': metrics
                }
                self.results.append(result)
                
                if metrics['composite_score'] > best_score:
                    best_score = metrics['composite_score']
                    best_config = config
                
                print(f"  Score: {metrics['composite_score']:.3f}")
                
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(f"{output_dir}/tuning_results.json", 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        if best_config:
            with open(f"{output_dir}/best_config.yaml", 'w') as f:
                yaml.dump(best_config, f, default_flow_style=False)
            
            print(f"\nBest configuration saved to {output_dir}/best_config.yaml")
            print(f"Best composite score: {best_score:.3f}")
        
        return best_config, self.results


def main():
    parser = argparse.ArgumentParser(description='Auto-tune RAG parameters')
    parser.add_argument('--queries', required=True, help='Path to test queries file')
    parser.add_argument('--output', default='configs/auto_tuned', help='Output directory')
    parser.add_argument('--config', help='Base config file path')
    
    args = parser.parse_args()
    
    tuner = RAGTuner(args.config)
    best_config, results = tuner.tune(args.queries, args.output)
    
    print(f"\nTuning complete. Results saved to {args.output}/")


if __name__ == "__main__":
    main()
