"""
AI Overnight Triage & First-Responder Agent for Vireo Audio.
Uses Groq LLM (with fallback) to:
- Accurately classify intent & extract entities (Order ID, SKU, Urgency)
- Cross-reference orders.csv, products.csv, customers.csv
- Check Section 5 policy constraints (prevent double refund/replacement)
- Generate personalized, immediate first-responses (<30 sec) to halt SLA breaches
- Route accurately to avoid internal transfers (Rs 305/transfer)
"""

import os
import re
import json
from typing import Dict, Any, Optional
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Pre-defined valid categories matching tickets.csv ground truth
VALID_CATEGORIES = [
    "Delivery & Shipping",
    "Billing & Payments",
    "Returns & Refunds",
    "Connectivity",
    "Charging & Battery",
    "Audio Quality",
    "Warranty & Repair",
    "Product Enquiry",
    "Account & Login",
    "App & Firmware",
    "Other"
]

TEAM_ROUTING = {
    "Delivery & Shipping": "Logistics",
    "Billing & Payments": "Billing",
    "Returns & Refunds": "Returns Desk",
    "Warranty & Repair": "Escalations & Warranty",
    "Connectivity": "Chat Frontline",
    "Charging & Battery": "Chat Frontline",
    "Audio Quality": "Chat Frontline",
    "Product Enquiry": "Chat Frontline",
    "Account & Login": "Chat Frontline",
    "App & Firmware": "Chat Frontline",
    "Other": "Chat Frontline"
}


class VireoTriageAgent:
    def __init__(self, orders_df: pd.DataFrame, products_df: pd.DataFrame, customers_df: pd.DataFrame, tickets_df: Optional[pd.DataFrame] = None):
        self.orders = orders_df
        self.products = products_df
        self.customers = customers_df
        self.tickets = tickets_df
        
        # Initialize Groq client
        self.client = None
        self.model_name = "openai/gpt-oss-120b"
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=groq_api_key)
            except Exception as e:
                print(f"[Warning] Groq initialization failed: {e}. Using deterministic rule fallback.")

    def _extract_order_regex(self, text: str) -> Optional[str]:
        match = re.search(r'\b(VR\d{6})\b', text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def analyze_message_llm(self, message: str) -> Dict[str, Any]:
        """Calls Groq LLM to extract category, entity, and urgency."""
        if not self.client:
            return self._heuristic_fallback(message)

        prompt = f"""You are the automated intake AI for Vireo Audio (Bengaluru), an Indian consumer electronics brand.
Analyze the customer support message and classify it into EXACTLY ONE category.

Category Definitions:
- Delivery & Shipping: Tracking, package delay, courier issues, wrong item received, address update, delivery date.
- Billing & Payments: Invoices, payment failed, deduction without order, double charge, refund status.
- Returns & Refunds: Cancellation before dispatch, return pickup, DOA within 7 days, replacement request.
- Connectivity: Bluetooth pairing, device connection drops, phone sync, Bluetooth range.
- Charging & Battery: Battery draining fast, earbud/case not charging, heating while charging, won't turn on.
- Audio Quality: Static noise, crackling, low volume, mic not working, bass imbalance.
- Warranty & Repair: In-warranty repair, service center, RMA, warranty claim for broken device.
- App & Firmware: Companion app crash, firmware update stuck/failed, software bugs.
- Account & Login: OTP not received, password reset, account login issues.
- Product Enquiry: Specifications, compatibility, price, launch queries.
- Other: General feedback, uncategorized inquiries.

Customer Message:
\"\"\"{message}\"\"\"

Respond with strictly valid JSON only:
{{
  "category": "one exact category from the list above",
  "intent": "brief description of customer goal",
  "order_id": "VR followed by 6 digits (e.g. VR892525) if present, else null",
  "product_mentioned": "product name or SKU if present, else null",
  "urgency": "High" or "Normal" or "Low",
  "summary": "1-sentence issue summary"
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a precise support triage classifier. Always output raw JSON only, starting with { and ending with }."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=250
            )
            raw_content = response.choices[0].message.content.strip()
            
            # Robust JSON extraction
            json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(raw_content)
            
            # Normalize category
            if data.get("category") not in VALID_CATEGORIES:
                data["category"] = self._match_closest_category(data.get("category", ""))
                
            # Regex backup for Order ID if present in message
            regex_order = self._extract_order_regex(message)
            if regex_order:
                data["order_id"] = regex_order

            return data
        except Exception as e:
            return self._heuristic_fallback(message)

    def _match_closest_category(self, cat: str) -> str:
        cat_lower = str(cat).lower()
        if "delivery" in cat_lower or "ship" in cat_lower or "track" in cat_lower:
            return "Delivery & Shipping"
        elif "bill" in cat_lower or "pay" in cat_lower or "invoice" in cat_lower:
            return "Billing & Payments"
        elif "refund" in cat_lower or "return" in cat_lower or "cancel" in cat_lower:
            return "Returns & Refunds"
        elif "connect" in cat_lower or "bluetooth" in cat_lower or "pair" in cat_lower:
            return "Connectivity"
        elif "charg" in cat_lower or "battery" in cat_lower:
            return "Charging & Battery"
        elif "audio" in cat_lower or "sound" in cat_lower or "noise" in cat_lower or "mic" in cat_lower:
            return "Audio Quality"
        elif "warranty" in cat_lower or "repair" in cat_lower or "rma" in cat_lower:
            return "Warranty & Repair"
        elif "login" in cat_lower or "otp" in cat_lower or "account" in cat_lower:
            return "Account & Login"
        elif "app" in cat_lower or "firmware" in cat_lower:
            return "App & Firmware"
        return "Other"

    def _heuristic_fallback(self, message: str) -> Dict[str, Any]:
        """Deterministic fallback when API is offline or exhausted."""
        order_id = self._extract_order_regex(message)
        cat = self._match_closest_category(message)
        return {
            "category": cat,
            "intent": "Customer inquiry",
            "order_id": order_id,
            "product_mentioned": None,
            "urgency": "High" if "urgent" in message.lower() or "asap" in message.lower() else "Normal",
            "summary": message[:80] + "..."
        }

    def enrich_context(self, analysis: Dict[str, Any], customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Enriches analysis with order, product, and customer policy context."""
        context = {
            "order_details": None,
            "product_details": None,
            "customer_details": None,
            "policy_alerts": []
        }
        
        # 1. Order lookup
        order_id = analysis.get("order_id")
        if order_id and not self.orders.empty:
            order_rows = self.orders[self.orders['order_id'].str.upper() == order_id.upper()]
            if not order_rows.empty:
                order_row = order_rows.iloc[0]
                context["order_details"] = {
                    "order_id": order_row['order_id'],
                    "order_date": order_row['order_date'],
                    "sku": order_row['sku'],
                    "qty": int(order_row['qty']),
                    "order_value_inr": float(order_row['order_value_inr']),
                    "channel": order_row['channel'],
                    "lot_code": order_row['lot_code']
                }
                # Overwrite customer_id if order specifies one
                customer_id = order_row['customer_id']

                # Product lookup from order SKU
                sku = order_row['sku']
                prod_rows = self.products[self.products['sku'] == sku]
                if not prod_rows.empty:
                    prod = prod_rows.iloc[0]
                    context["product_details"] = {
                        "sku": prod['sku'],
                        "product_name": prod['product_name'],
                        "retail_price_inr": float(prod['retail_price_inr']),
                        "warranty_months": int(prod['warranty_months'])
                    }

        # 2. Customer Care+ check
        if customer_id and not self.customers.empty:
            cust_rows = self.customers[self.customers['customer_id'] == customer_id]
            if not cust_rows.empty:
                cust = cust_rows.iloc[0]
                context["customer_details"] = {
                    "customer_id": cust['customer_id'],
                    "name": cust['name'],
                    "care_plus": cust['care_plus'] == 'Y',
                    "city": cust['city']
                }
                if cust['care_plus'] == 'Y':
                    context["policy_alerts"].append("VIP Customer: Care+ Member (Priority Queue)")

        # 3. Double Refund / Replacement Risk Check (Section 5)
        if order_id and self.tickets is not None and not self.tickets.empty:
            prior_tickets = self.tickets[self.tickets['order_id'] == order_id]
            has_prior_refund = (prior_tickets['refund_amount_inr'] > 0).any()
            has_prior_replacement = (prior_tickets['replacement_issued'] == 'Y').any()
            if has_prior_refund and has_prior_replacement:
                context["policy_alerts"].append("CRITICAL: Prior refund AND replacement already issued for this order!")
            elif has_prior_refund:
                context["policy_alerts"].append("POLICY WARNING: Prior refund already issued for this order.")
            elif has_prior_replacement:
                context["policy_alerts"].append("POLICY WARNING: Prior replacement already issued for this order.")

        return context

    def generate_first_response(self, customer_message: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Generates an instant, highly personalized, and context-aware first response.
        Leverages Groq LLM with retrieved order and product facts, with fallback to rule templates.
        """
        category = analysis.get("category", "Other")
        order_info = context.get("order_details")
        cust_info = context.get("customer_details")
        prod_info = context.get("product_details")
        cust_name = cust_info['name'] if cust_info else "there"
        policy_alerts = context.get("policy_alerts", [])
        
        # If client is available, generate a truly personalized response addressing the customer's exact words
        if self.client:
            prompt = f"""You are an empathetic, knowledgeable support agent at Vireo Audio (Bengaluru), an Indian consumer electronics brand.
The customer has reached out via live chat. Generate an immediate, genuinely helpful, and personalized first response.

Customer Name: {cust_name}
Customer Message: "{customer_message}"
Issue Category: {category}
Assigned Team: {TEAM_ROUTING.get(category, 'Chat Frontline')}
Customer VIP Status: {'Care+ VIP Member' if cust_info and cust_info.get('care_plus') else 'Standard'}

Known Order Details: {json.dumps(order_info) if order_info else 'Not provided yet'}
Known Product Details: {json.dumps(prod_info) if prod_info else 'Not provided yet'}
Policy / Risk Alerts: {', '.join(policy_alerts) if policy_alerts else 'None'}

Response Guidelines:
1. Address the customer's EXACT question, complaint, or request directly. Do NOT use generic canned boilerplate.
2. If order details are available, acknowledge their order date, product name, and current handling.
3. If they asked about an order/delivery but didn't provide an order ID, politely ask for their 8-character Order ID (e.g. VR892525).
4. If they report a technical problem (audio crackle, pairing, battery), provide 1-2 actionable, relevant troubleshooting steps right away.
5. If they ask about returns/warranty, reference Vireo's 7-day DOA replacement and 1-year product warranty policy.
6. Tone: Warm, professional, helpful, Indian-market friendly (use INR/Rupees if discussing prices).
7. Keep length between 2 to 4 sentences. Always finish your thoughts with a complete final sentence.
8. Output ONLY the response text to send directly to the customer. No quotes, no intro tags.
"""
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a warm, helpful, and concise customer support representative for Vireo Audio. Always write complete sentences."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                generated_text = response.choices[0].message.content.strip()
                if generated_text and len(generated_text) > 20:
                    return generated_text
            except Exception as e:
                # Fall back to heuristic templates if LLM call fails
                pass

        # Robust Fallback Templates (used only if offline or LLM fails)
        if category == "Delivery & Shipping" and order_info:
            return (
                f"Hello {cust_name}, thank you for reaching out to Vireo Support! "
                f"We have located your order {order_info['order_id']} placed on {order_info['order_date']} "
                f"for the {prod_info['product_name'] if prod_info else 'product'}. "
                f"Our logistics team is actively tracking dispatch with our courier partner. "
                f"If you need an immediate address modification, please reply with 'EDIT ADDRESS'."
            )
        elif category == "Billing & Payments":
            order_ref = f"for order {order_info['order_id']} " if order_info else ""
            return (
                f"Hello {cust_name}, thank you for contacting Vireo Audio. "
                f"We have logged your payment/invoice query {order_ref}and our Billing Desk has been assigned. "
                f"Invoices can be downloaded directly from your account dashboard under 'My Orders'."
            )
        elif category in ["Connectivity", "Audio Quality", "Charging & Battery"]:
            prod_name = prod_info['product_name'] if prod_info else "your Vireo device"
            return (
                f"Hello {cust_name}, we are sorry you are having trouble with {prod_name}. "
                f"While a specialist reviews your ticket, please try placing the earbuds in the charging case, "
                f"forgetting the device from your Bluetooth settings, and holding the case button for 10 seconds to reset. "
                f"If this does not resolve it, our audio specialist will assist you promptly."
            )
        elif category == "Returns & Refunds":
            return (
                f"Hello {cust_name}, thank you for reaching out. We have logged your return/refund request. "
                f"Under Vireo's 7-day DOA and warranty policy, all returns undergo a reverse-pickup QC inspection. "
                f"Our Returns Desk will verify your details and schedule pickup within our morning window."
            )
        else:
            return (
                f"Hello {cust_name}, thank you for reaching out to Vireo Audio Support. "
                f"Your request regarding {category.lower()} has been assigned to our {TEAM_ROUTING.get(category, 'Support')} team. "
                f"A specialist is reviewing your message and will assist you shortly."
            )

    def process_ticket(self, customer_message: str, customer_id: Optional[str] = None, known_order_id: Optional[str] = None) -> Dict[str, Any]:
        """End-to-end processing pipeline for a single incoming ticket."""
        analysis = self.analyze_message_llm(customer_message)
        
        # If order ID was already known in ticket metadata, use it as fallback
        if not analysis.get("order_id") and known_order_id:
            analysis["order_id"] = str(known_order_id).strip().upper()
            
        context = self.enrich_context(analysis, customer_id)
        suggested_response = self.generate_first_response(customer_message, analysis, context)
        suggested_team = TEAM_ROUTING.get(analysis['category'], 'Chat Frontline')
        
        return {
            "customer_message": customer_message,
            "category": analysis["category"],
            "intent": analysis.get("intent"),
            "extracted_order_id": analysis.get("order_id"),
            "urgency": analysis.get("urgency", "Normal"),
            "suggested_team": suggested_team,
            "order_context": context["order_details"],
            "policy_alerts": context["policy_alerts"],
            "automated_first_response": suggested_response
        }
