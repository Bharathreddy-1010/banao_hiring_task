"""
Data Loader & Preprocessor for Vireo Audio Support Desk.
Handles:
- Deduplication between legacy_fd and helpdesk
- UTC to IST (+5:30) conversion for accurate shift alignment
- Channel SLA targets and breach determination
- Roster and order enrichment
"""

import os
import re
import pandas as pd
import numpy as np

# Resolve default data directory (points to data_given if present, else fallback)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data_given') if os.path.exists(os.path.join(BASE_DIR, 'data_given')) else BASE_DIR

# Policy SLA Targets (Section 3)
SLA_TARGET_MINUTES = {
    'chat': 15,          # 15 minutes
    'voice': 120,        # 2 hours
    'social': 240,       # 4 hours
    'email': 480         # 8 hours
}

# Contact Costs (Section 4)
CONTACT_COSTS = {
    'chat': 210,
    'email': 260,
    'social': 240,
    'voice': 520
}

BREACH_CREDIT_INR = 350
TRANSFER_COST_INR = 305


def get_shift_ist(hour: int) -> str:
    """Returns shift name based on IST hour (Section 7)."""
    if 6 <= hour < 14:
        return 'Morning'
    elif 14 <= hour < 22:
        return 'Day'
    else:
        return 'Night'


def load_and_clean_tickets(tickets_path: str = None) -> pd.DataFrame:
    """
    Loads tickets.csv, removes reconciliation duplicates,
    and calculates accurate IST timestamps and SLA breach status.
    """
    if tickets_path is None:
        tickets_path = os.path.join(DATA_DIR, 'tickets.csv') if os.path.exists(os.path.join(DATA_DIR, 'tickets.csv')) else 'tickets.csv'
    df = pd.read_csv(tickets_path)
    
    # 1. Deduplicate: Reconciled legacy tickets appear under both systems.
    # Keep the latest 'helpdesk' version.
    df = df.sort_values('source_system').drop_duplicates(subset=['ticket_id'], keep='last').copy()
    
    # 2. Timezone conversion: API exports UTC. Policy shifts are in IST (+5:30).
    for col in ['created_at', 'first_response_at', 'resolved_at']:
        df[col + '_utc'] = pd.to_datetime(df[col], errors='coerce')
        df[col + '_ist'] = df[col + '_utc'] + pd.Timedelta(hours=5, minutes=30)
    
    df['created_hour_ist'] = df['created_at_ist'].dt.hour
    df['shift_ist'] = df['created_hour_ist'].apply(get_shift_ist)
    df['created_date_ist'] = df['created_at_ist'].dt.date
    df['created_week_ist'] = df['created_at_ist'].dt.to_period('W-SUN')
    df['created_quarter'] = df['created_at_ist'].dt.to_period('Q')
    
    # 3. Response time and SLA calculation
    df['response_time_minutes'] = (df['first_response_at_utc'] - df['created_at_utc']).dt.total_seconds() / 60.0
    df['sla_target_minutes'] = df['channel'].map(SLA_TARGET_MINUTES)
    df['is_breach'] = df['response_time_minutes'] > df['sla_target_minutes']
    
    # Handle time (from first response to resolution)
    df['handle_time_minutes'] = (df['resolved_at_utc'] - df['first_response_at_utc']).dt.total_seconds() / 60.0
    
    # 4. Period marker: Indore Night Shift decommissioned after 2025-06-29
    df['roster_period'] = np.where(df['created_at_ist'] < '2025-07-01', 'Pre-July 2025 (Staffed Night)', 'Post-July 2025 (Unstaffed Night)')
    
    # 5. Extract Order ID from customer message if missing in column
    order_regex = re.compile(r'\b(VR\d{6})\b', re.IGNORECASE)
    extracted_order = df['customer_message'].dropna().apply(
        lambda msg: order_regex.search(msg).group(1).upper() if order_regex.search(msg) else np.nan
    )
    df['extracted_order_id'] = df['order_id'].fillna(extracted_order)
    
    return df


def load_reference_data(data_dir: str = None):
    """Loads agents, orders, customers, and products tables from data_given."""
    if data_dir is None:
        data_dir = DATA_DIR if os.path.exists(os.path.join(DATA_DIR, 'agents.csv')) else '.'
    agents = pd.read_csv(os.path.join(data_dir, 'agents.csv'))
    orders = pd.read_csv(os.path.join(data_dir, 'orders.csv'))
    customers = pd.read_csv(os.path.join(data_dir, 'customers.csv'))
    products = pd.read_csv(os.path.join(data_dir, 'products.csv'))
    return agents, orders, customers, products
