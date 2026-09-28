import pandas as pd
from groq import Groq
import os
from dotenv import load_dotenv

def main():
    # Load environment variables from the .env file
    load_dotenv()
    
    # Initialize Groq Client (it will automatically find GROQ_API_KEY from the environment)
    client = Groq()

    print("Loading and cleaning data...")
    tickets_path = os.path.join('data_given', 'tickets.csv') if os.path.exists(os.path.join('data_given', 'tickets.csv')) else 'tickets.csv'
    tickets = pd.read_csv(tickets_path)
    
    # Drop duplicates caused by the system migration
    tickets = tickets.sort_values('source_system').drop_duplicates(subset=['ticket_id'], keep='last')
    
    # Convert UTC to IST (add 5.5 hours)
    tickets['created_at_ist'] = pd.to_datetime(tickets['created_at'], format='mixed') + pd.Timedelta(hours=5, minutes=30)
    tickets['created_hour'] = tickets['created_at_ist'].dt.hour
    
    # Filter for Chat tickets created during the Night Shift (22:00 to 06:00 IST)
    night_chats = tickets[
        (tickets['channel'] == 'chat') & 
        ((tickets['created_hour'] >= 22) | (tickets['created_hour'] <= 5))
    ].copy()
    
    sample_messages = night_chats['customer_message'].dropna().head(15).tolist()
    print(f"Found {len(night_chats)} overnight chat tickets. Analyzing a sample with Llama-3...\n")
    
    # Use Groq AI to categorize the root cause
    for msg in sample_messages:
        prompt = f"""
        Read this customer support message. Categorize it into EXACTLY ONE of these buckets:
        - Order Status / Tracking
        - Cancellation Request
        - Refund Inquiry
        - Technical Issue
        - Other
        
        Reply ONLY with the exact bucket name. No other text.
        
        Message: "{msg}"
        """
        
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-120b", 
                temperature=0, 
                max_tokens=20
            )
            
            category = response.choices[0].message.content.strip()
            clean_msg = msg.replace('\n', ' ')[:70]
            print(f"[{category.ljust(25)}] | {clean_msg}...")
            
        except Exception as e:
            print(f"[ERROR] API Call Failed: {e}")

if __name__ == "__main__":
    main()