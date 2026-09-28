"""
Vireo Audio Support AI — Main Command-Line Interface.
Usage:
  python app.py audit                  # Run the complete SLA breach & root cause audit
  python app.py triage [--limit N]     # Run overnight ticket triage & auto-responder demonstration
  python app.py evaluate [--sample N]  # Run the evaluation benchmark suite
  python app.py interactive            # Interactive message test prompt
"""

import sys
import argparse
import json
import pandas as pd
from src.data_loader import load_and_clean_tickets, load_reference_data
from src.sla_audit import run_sla_audit, format_audit_report
from src.triage_agent import VireoTriageAgent
from src.evaluator import run_benchmark


def cmd_audit(args):
    print("Loading Vireo Audio dataset and calculating accurate IST timestamps...")
    df = load_and_clean_tickets()
    agents, _, _, _ = load_reference_data()
    audit_data = run_sla_audit(df, agents)
    print(format_audit_report(audit_data))


def cmd_triage(args):
    print(f"Loading data and processing up to {args.limit} overnight chat tickets...")
    df = load_and_clean_tickets()
    agents, orders, customers, products = load_reference_data()
    agent = VireoTriageAgent(orders, products, customers, df)
    
    # Filter for post-July unstaffed night chat tickets
    night_chats = df[
        (df['created_at_ist'] >= '2025-07-01') &
        (df['channel'] == 'chat') &
        (df['shift_ist'] == 'Night') &
        df['customer_message'].notna()
    ].head(args.limit)
    
    print("=" * 70)
    print(f"PROCESSING {len(night_chats)} OVERNIGHT TICKETS THROUGH VIREO AI")
    print("=" * 70)
    
    for i, (_, row) in enumerate(night_chats.iterrows(), 1):
        msg = row['customer_message']
        cust_id = row['customer_id'] if 'customer_id' in row and pd.notna(row['customer_id']) else None
        order_id = row['extracted_order_id'] if 'extracted_order_id' in row and pd.notna(row['extracted_order_id']) else None
        
        result = agent.process_ticket(msg, customer_id=cust_id, known_order_id=order_id)
        
        print(f"\n[{i}/{len(night_chats)}] TICKET: {row['ticket_id']} | Channel: Chat | Created (IST): {row['created_at_ist']}")
        print(f"Customer Message:\n  \"{msg.replace(chr(10), ' ')[:100]}...\"")
        print(f"-> Predicted Category: {result['category']}")
        print(f"-> Extracted Order ID: {result['extracted_order_id']}")
        print(f"-> Target Route:       {result['suggested_team']}")
        if result['policy_alerts']:
            print(f"-> Policy Alerts:      {', '.join(result['policy_alerts'])}")
        print(f"-> Automated First Response (<30s turnaround):\n  {result['automated_first_response']}")
        print("-" * 70)


def cmd_evaluate(args):
    print(f"Running automated evaluation benchmark on N={args.sample} tickets...")
    benchmark_results = run_benchmark(sample_size=args.sample)
    print("\n" + "=" * 60)
    print("BENCHMARK ACCURACY & PERFORMANCE RESULTS")
    print("=" * 60)
    print(f"Sample Size:                  {benchmark_results['sample_size']} tickets")
    print(f"Category Accuracy:            {benchmark_results['category_accuracy_pct']}%")
    print(f"Order ID Extraction Accuracy: {benchmark_results['order_extraction_accuracy_pct']}%")
    print(f"Average Turnaround Latency:   {benchmark_results['avg_latency_ms']} ms")
    print(f"Total Prediction Errors:      {benchmark_results['total_errors']}")
    print("=" * 60)
    
    with open("eval_results.json", "w") as f:
        json.dump(benchmark_results, f, indent=2)
    print("Benchmark summary exported to eval_results.json\n")


def cmd_interactive(args):
    print("\nEntering Interactive Mode. Type a customer support message (or 'exit' to quit):")
    agents, orders, customers, products = load_reference_data()
    agent = VireoTriageAgent(orders, products, customers)
    
    while True:
        try:
            msg = input("\nCustomer > ").strip()
            if not msg or msg.lower() in ['exit', 'quit']:
                break
            
            result = agent.process_ticket(msg)
            print(f"\n[AI Triage Result]")
            print(f"  Category:       {result['category']}")
            print(f"  Extracted Order:{result['extracted_order_id']}")
            print(f"  Routed Team:    {result['suggested_team']}")
            if result['policy_alerts']:
                print(f"  Policy Alerts:  {', '.join(result['policy_alerts'])}")
            print(f"\n[Automated Response]\n{result['automated_first_response']}\n")
        except (KeyboardInterrupt, EOFError):
            break


def main():
    parser = argparse.ArgumentParser(description="Vireo Audio Support AI Desk Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Audit command
    subparsers.add_parser("audit", help="Run SLA breach root-cause and queue audit")
    
    # Triage command
    p_triage = subparsers.add_parser("triage", help="Triage overnight tickets and demonstrate automated first-responder")
    p_triage.add_argument("--limit", type=int, default=5, help="Number of tickets to process (default: 5)")
    
    # Evaluate command
    p_eval = subparsers.add_parser("evaluate", help="Run evaluation benchmark suite")
    p_eval.add_argument("--sample", type=int, default=30, help="Benchmark sample size (default: 30)")
    
    # Interactive command
    subparsers.add_parser("interactive", help="Interactive testing prompt")
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    if args.command == "audit":
        cmd_audit(args)
    elif args.command == "triage":
        cmd_triage(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "interactive":
        cmd_interactive(args)


if __name__ == "__main__":
    main()
