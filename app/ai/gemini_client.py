import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

class GeminiClient:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
        self.model = self.models_to_try[0]
        self.system_prompt = """You are Nexus AI, the intelligent assistant for Nexus ERP - an enterprise resource planning system for Indian businesses.

CORE IDENTITY:
- You are a knowledgeable, helpful business analyst embedded in an ERP system
- You specialize in Indian business operations (currency: INR, format: lakh/crore like Rs.1,00,000)
- You provide actionable insights, not just data

CAPABILITIES:
1. Answer questions about business data (sales, expenses, inventory, employees, projects)
2. Analyze trends and provide forecasts
3. Identify anomalies and suggest actions
4. Generate business summaries and reports
5. Help with inventory management decisions
6. Provide financial insights (P&L, expense breakdowns)

RESPONSE STYLE:
- Be concise but informative
- Use Indian number formatting (Rs. 1,00,000 / 1.5 lakh / 2.3 crore)
- Use "Rs." instead of the rupee symbol to avoid encoding issues
- Include specific numbers when available
- Suggest actionable next steps
- Use bullet points for clarity
- When data is provided, reference specific items by name/ID

IMPORTANT RULES:
- Never fabricate data - only use what's provided in the context
- If you don't have enough data, say so clearly
- For sensitive operations, remind users to verify before acting
- Always respond in English
- Format currency as Rs. X,XX,XXX.XX (Indian style)
- NEVER use the Rs. symbol - always use "Rs." instead"""

    def _generate(self, prompt):
        for model_name in self.models_to_try:
            url = f"{self.base_url}/{model_name}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": 2048
                }
            }
            try:
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if 'candidates' in data and data['candidates']:
                        text = data['candidates'][0]['content']['parts'][0]['text']
                        text = text.replace('\u20b9', 'Rs.')
                        self.model = model_name
                        return {'success': True, 'text': text, 'model': model_name}
                elif resp.status_code == 429:
                    continue
                else:
                    continue
            except Exception:
                continue
        return {'success': False, 'text': 'All Gemini models are currently unavailable. Please try again later.', 'model': None}

    def chat(self, user_message, business_context=""):
        full_prompt = f"{self.system_prompt}\n\n---\nBUSINESS DATA CONTEXT:\n{business_context}\n---\n\nUser: {user_message}\n\nNexus AI:"
        result = self._generate(full_prompt)
        return {
            'success': result['success'],
            'response': result['text'],
            'model': result['model'] or 'gemini'
        }

    def analyze_data(self, data_summary, analysis_type="general"):
        analysis_prompts = {
            "sales": "Analyze the following sales data. Identify top performers, trends, and opportunities. Provide specific recommendations.",
            "expense": "Analyze the following expense data. Identify unusual patterns, cost-saving opportunities, and budget concerns.",
            "inventory": "Analyze the following inventory data. Identify reorder needs, dead stock, and optimization opportunities.",
            "forecast": "Based on the following historical data, provide a forecast for the next period. Include confidence levels.",
            "anomaly": "Identify any anomalies or unusual patterns in the following data. Flag items that need attention.",
            "summary": "Generate an executive summary of the following business data. Highlight key metrics and action items.",
            "general": "Analyze the following business data and provide actionable insights."
        }
        prompt = f"""{self.system_prompt}

ANALYSIS TASK: {analysis_prompts.get(analysis_type, analysis_prompts['general'])}

DATA TO ANALYZE:
{data_summary}

Provide your analysis in the following JSON format:
{{
    "summary": "Brief executive summary (2-3 sentences)",
    "key_findings": ["finding 1", "finding 2", "finding 3"],
    "anomalies": ["anomaly 1" or empty array],
    "recommendations": ["recommendation 1", "recommendation 2"],
    "metrics": {{"metric_name": "value"}}
}}

Respond with valid JSON only."""

        result = self._generate(prompt)
        if result['success']:
            text = result['text'].strip()
            if text.startswith('```json'):
                text = text[7:-3]
            elif text.startswith('```'):
                text = text[3:-3]
            try:
                analysis = json.loads(text)
            except json.JSONDecodeError:
                analysis = {
                    'summary': text,
                    'key_findings': [],
                    'anomalies': [],
                    'recommendations': [],
                    'metrics': {}
                }
            return {'success': True, 'analysis': analysis, 'model': result['model']}
        else:
            return {
                'success': False,
                'analysis': {
                    'summary': result['text'],
                    'key_findings': [],
                    'anomalies': [],
                    'recommendations': [],
                    'metrics': {}
                },
                'error': result['text']
            }

    def categorize_expense(self, description, amount, existing_categories):
        prompt = f"""Categorize this business expense into one of the existing categories.

Expense Description: {description}
Amount: Rs.{amount:,.2f}

Existing Categories: {', '.join(existing_categories)}

Respond with JSON:
{{
    "category": "most likely category",
    "confidence": 0.0-1.0,
    "is_anomalous": true/false,
    "reason": "brief explanation"
}}"""
        result = self._generate(prompt)
        if result['success']:
            text = result['text'].strip()
            if text.startswith('```json'):
                text = text[7:-3]
            elif text.startswith('```'):
                text = text[3:-3]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return {"category": existing_categories[0] if existing_categories else "Other", "confidence": 0.5, "is_anomalous": False, "reason": "Auto-categorized"}

    def generate_forecast(self, historical_data, metric_name):
        prompt = f"""Based on the following historical {metric_name} data, generate a simple forecast for the next month.

Historical Data (chronological):
{historical_data}

Respond with JSON:
{{
    "forecast_value": predicted_number,
    "confidence": "high/medium/low",
    "trend": "increasing/decreasing/stable",
    "reasoning": "brief explanation",
    "percentage_change": estimated_percentage_change
}}"""
        result = self._generate(prompt)
        if result['success']:
            text = result['text'].strip()
            if text.startswith('```json'):
                text = text[7:-3]
            elif text.startswith('```'):
                text = text[3:-3]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return {"forecast_value": 0, "confidence": "low", "trend": "stable", "reasoning": "Unable to generate forecast", "percentage_change": 0}
