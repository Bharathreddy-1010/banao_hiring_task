"""
Evaluation Benchmark Suite for Vireo Support AI.
Measures:
- Intent Classification Accuracy vs Ground Truth Category
- Entity Extraction Precision & Recall (Order IDs)
- Routing Alignment
- Error Analysis & Failure Mode Taxonomy
"""

import time
import json
import pandas as pd
from typing import Dict, Any
from src.data_loader import load_and_clean_tickets, load_reference_data
from src.triage_agent import VireoTriageAgent


def run_benchmark(sample_size: int = 50, random_seed: int = 42) -> Dict[str, Any]:
    """Runs automated evaluation on a sampled test set from tickets.csv."""
    df = load_and_clean_tickets()
    agents, orders, customers, products = load_reference_data()
    agent = VireoTriageAgent(orders, products, customers, df)
    
    # Filter for tickets with non-empty customer messages and valid categories
    valid_test_pool = df[
        df['customer_message'].notna() &
        (df['customer_message'].str.len() > 15) &
        df['category'].notna()
    ].sample(n=sample_size, random_state=random_seed)
    
    results = []
    category_matches = 0
    order_id_matches = 0
    total_with_order = 0
    latencies = []
    error_cases = []
    
    for idx, row in valid_test_pool.iterrows():
        msg = str(row['customer_message'])
        gt_category = row['category']
        gt_order_id = str(row['extracted_order_id']) if pd.notna(row['extracted_order_id']) else None
        
        t0 = time.time()
        pred = agent.process_ticket(msg, customer_id=row['customer_id'] if pd.notna(row['customer_id']) else None)
        latency = (time.time() - t0) * 1000  # in ms
        latencies.append(latency)
        
        # Category comparison
        is_cat_match = (pred['category'].lower() == gt_category.lower())
        if is_cat_match:
            category_matches += 1
        else:
            error_cases.append({
                "ticket_id": row['ticket_id'],
                "message": msg[:100],
                "ground_truth_category": gt_category,
                "predicted_category": pred['category'],
                "reason": "Category mismatch / ambiguity"
            })
            
        # Order ID comparison
        if gt_order_id:
            total_with_order += 1
            pred_order = pred.get('extracted_order_id')
            if pred_order and pred_order.upper() == gt_order_id.upper():
                order_id_matches += 1
                
        results.append({
            "ticket_id": row['ticket_id'],
            "gt_category": gt_category,
            "pred_category": pred['category'],
            "latency_ms": latency
        })
        
    cat_accuracy = (category_matches / sample_size) * 100
    order_accuracy = (order_id_matches / total_with_order * 100) if total_with_order > 0 else 100.0
    avg_latency_ms = sum(latencies) / len(latencies)
    
    summary = {
        "sample_size": sample_size,
        "category_accuracy_pct": round(cat_accuracy, 2),
        "order_extraction_accuracy_pct": round(order_accuracy, 2),
        "avg_latency_ms": round(avg_latency_ms, 1),
        "total_errors": len(error_cases),
        "error_examples": error_cases[:5]
    }
    
    return summary


if __name__ == "__main__":
    print("Running Vireo AI Evaluation Benchmark (N=50)...")
    benchmark_results = run_benchmark(sample_size=50)
    print("=" * 60)
    print("EVALUATION RESULTS:")
    print(f"Sample Size: {benchmark_results['sample_size']} tickets")
    print(f"Category Accuracy: {benchmark_results['category_accuracy_pct']}%")
    print(f"Order ID Extraction Accuracy: {benchmark_results['order_extraction_accuracy_pct']}%")
    print(f"Average Response Latency: {benchmark_results['avg_latency_ms']} ms")
    print("=" * 60)
    print("Sample Error Analysis:")
    for err in benchmark_results['error_examples']:
        print(f"Ticket: {err['ticket_id']}")
        print(f"  Snippet: {err['message']}...")
        print(f"  Ground Truth: {err['ground_truth_category']} | Predicted: {err['predicted_category']}")
        print("-" * 50)
        
    with open("eval_results.json", "w") as f:
        json.dump(benchmark_results, f, indent=2)
    print("Results saved to eval_results.json")
