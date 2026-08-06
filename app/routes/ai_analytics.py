from flask import Blueprint, render_template, session, redirect, url_for, jsonify
from app.utils import login_required, manager_or_admin_required, log_audit
from app.ai.gemini_client import GeminiClient
from app.ai.data_context import DataContext

ai_analytics_bp = Blueprint('ai_analytics', __name__)


@ai_analytics_bp.route('/ai-analytics')
@manager_or_admin_required
def ai_analytics_page():
    try:
        ctx = DataContext()
        full_context = ctx.get_full_context()
        context_text = ctx.format_context_for_ai(full_context)

        client = GeminiClient()

        sales_analysis = client.analyze_data(context_text, "sales")
        expense_analysis = client.analyze_data(context_text, "expense")
        inventory_analysis = client.analyze_data(context_text, "inventory")
        summary = client.analyze_data(context_text, "summary")

        sales_forecast = None
        if full_context['sales']['monthly_sales']:
            history = "\n".join([
                f"{m['month']}: Rs.{m['revenue']:,.0f}"
                for m in full_context['sales']['monthly_sales']
            ])
            sales_forecast = client.generate_forecast(history, "revenue")

        log_audit(session['user_id'], "Generated AI analytics report")

        return render_template('ai_analytics.html',
                               full_context=full_context,
                               sales_analysis=sales_analysis,
                               expense_analysis=expense_analysis,
                               inventory_analysis=inventory_analysis,
                               summary=summary,
                               sales_forecast=sales_forecast)
    except Exception as e:
        return render_template('ai_analytics.html',
                               full_context={},
                               sales_analysis={'success': False, 'analysis': {'summary': f'Error: {str(e)}'}},
                               expense_analysis={'success': False, 'analysis': {'summary': 'Error loading analysis'}},
                               inventory_analysis={'success': False, 'analysis': {'summary': 'Error loading analysis'}},
                               summary={'success': False, 'analysis': {'summary': 'Error loading summary'}},
                               sales_forecast=None)


@ai_analytics_bp.route('/api/ai/analytics/refresh', methods=['POST'])
@manager_or_admin_required
def refresh_analytics():
    try:
        ctx = DataContext()
        full_context = ctx.get_full_context()
        context_text = ctx.format_context_for_ai(full_context)

        client = GeminiClient()

        analysis_type = 'general'
        result = client.analyze_data(context_text, analysis_type)

        return jsonify({'success': True, 'analysis': result.get('analysis', {})})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@ai_analytics_bp.route('/api/ai/forecast/<metric>')
@manager_or_admin_required
def get_forecast(metric):
    try:
        ctx = DataContext()

        if metric == 'sales':
            data = ctx.get_sales_context()
            if data['monthly_sales']:
                history = "\n".join([f"{m['month']}: Rs.{m['revenue']:,.0f}" for m in data['monthly_sales']])
                client = GeminiClient()
                forecast = client.generate_forecast(history, "revenue")
                return jsonify({'success': True, 'forecast': forecast})

        elif metric == 'expenses':
            data = ctx.get_expense_context()
            if data['monthly_expenses']:
                monthly = {}
                for row in data['monthly_expenses']:
                    month = row['month']
                    if month not in monthly:
                        monthly[month] = 0
                    monthly[month] += float(row['total'])
                history = "\n".join([f"{m}: Rs.{v:,.0f}" for m, v in sorted(monthly.items())])
                client = GeminiClient()
                forecast = client.generate_forecast(history, "expenses")
                return jsonify({'success': True, 'forecast': forecast})

        return jsonify({'success': False, 'error': 'Insufficient data for forecast'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
