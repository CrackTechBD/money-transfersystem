#!/usr/bin/env python3
"""
Simple Admin Dashboard for Fraud Management
Provides a web interface for viewing and managing fraud actions
"""

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import requests
import json
from typing import Optional

app = FastAPI(title="Fraud Admin Dashboard", version="1.0.0")

# Service URLs
FRAUD_ACTION_SERVICE_URL = "http://fraud_action_service:8007"
ANALYTICS_SERVICE_URL = "http://analytics_service:8000"

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main fraud management dashboard"""
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fraud Management Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 30px;
                margin-bottom: 20px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .header h1 {
                font-size: 2.5em;
                color: #2a5298;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 1.2em;
                color: #666;
            }
            .nav {
                display: flex;
                gap: 20px;
                justify-content: center;
                margin-top: 20px;
            }
            .nav-btn {
                background: #667eea;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                transition: all 0.3s ease;
                font-weight: 600;
            }
            .nav-btn:hover {
                background: #5a6fd8;
                transform: translateY(-2px);
            }
            .section {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                margin-bottom: 20px;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .section-header {
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white;
                padding: 20px 30px;
                font-size: 1.5em;
                font-weight: 600;
            }
            .section-content {
                padding: 30px;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .stat-card {
                background: white;
                border-radius: 12px;
                padding: 25px;
                text-align: center;
                border-left: 5px solid #667eea;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .stat-value {
                font-size: 2.2em;
                font-weight: bold;
                color: #2a5298;
                margin-bottom: 8px;
            }
            .stat-label {
                color: #666;
                font-size: 1em;
            }
            .btn {
                background: #667eea;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s ease;
            }
            .btn:hover {
                background: #5a6fd8;
            }
            .btn-danger {
                background: #dc3545;
            }
            .btn-danger:hover {
                background: #c82333;
            }
            .btn-success {
                background: #28a745;
            }
            .btn-success:hover {
                background: #218838;
            }
            .alert {
                padding: 15px;
                margin: 10px 0;
                border-radius: 6px;
                border-left: 5px solid;
            }
            .alert-critical {
                background: #f8d7da;
                border-color: #dc3545;
                color: #721c24;
            }
            .alert-medium {
                background: #fff3cd;
                border-color: #ffc107;
                color: #856404;
            }
            .alert-low {
                background: #d4edda;
                border-color: #28a745;
                color: #155724;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
            }
            tr:hover {
                background: #f5f5f5;
            }
            .status-pending {
                background: #ffc107;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.9em;
            }
            .status-approved {
                background: #28a745;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.9em;
            }
            .status-rejected {
                background: #dc3545;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.9em;
            }
        </style>
        <script>
            // Auto-refresh every 30 seconds
            setTimeout(function() {
                location.reload();
            }, 30000);
            
            function refreshSection(sectionId) {
                location.reload();
            }
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚨 Fraud Management Dashboard</h1>
                <p>Monitor and manage fraud detection actions in real-time</p>
                <div class="nav">
                    <a href="/alerts" class="nav-btn">View Alerts</a>
                    <a href="/review-queue" class="nav-btn">Review Queue</a>
                    <a href="/stats" class="nav-btn">Statistics</a>
                    <a href="/accounts" class="nav-btn">Account Status</a>
                </div>
            </div>

            <div class="section">
                <div class="section-header">📊 Fraud Statistics Overview</div>
                <div class="section-content">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value" id="pending-reviews">Loading...</div>
                            <div class="stat-label">Pending Reviews</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="frozen-accounts">Loading...</div>
                            <div class="stat-label">Frozen Accounts</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="total-alerts">Loading...</div>
                            <div class="stat-label">Active Alerts</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="actions-today">Loading...</div>
                            <div class="stat-label">Actions Today</div>
                        </div>
                    </div>
                    <p><strong>Note:</strong> This is a demo fraud management system. In production, you would have comprehensive dashboards, machine learning models, and integration with external fraud detection services.</p>
                </div>
            </div>

            <div class="section">
                <div class="section-header">🚨 Recent High-Priority Alerts</div>
                <div class="section-content" id="recent-alerts">
                    <p>Loading recent alerts...</p>
                </div>
            </div>

            <div class="section">
                <div class="section-header">📋 Manual Review Queue</div>
                <div class="section-content" id="review-queue">
                    <p>Loading review queue...</p>
                </div>
            </div>
        </div>

        <script>
            // Load fraud statistics
            async function loadStats() {
                try {
                    // Note: In a real implementation, these would be API calls
                    // For demo purposes, showing placeholder data
                    document.getElementById('pending-reviews').textContent = '3';
                    document.getElementById('frozen-accounts').textContent = '1';
                    document.getElementById('total-alerts').textContent = '15';
                    document.getElementById('actions-today').textContent = '7';
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }

            // Load recent alerts
            async function loadAlerts() {
                try {
                    const alertsHtml = `
                        <div class="alert alert-critical">
                            <strong>CRITICAL:</strong> High-risk payment detected (Score: 0.85) - Payment ID: abc123
                            <button class="btn btn-danger" style="float: right;">Investigate</button>
                        </div>
                        <div class="alert alert-medium">
                            <strong>REVIEW:</strong> Suspicious transaction pattern - User: jekopaul1
                            <button class="btn" style="float: right;">Review</button>
                        </div>
                        <div class="alert alert-low">
                            <strong>INFO:</strong> Payment processed normally (Score: 0.15) - Payment ID: def456
                        </div>
                    `;
                    document.getElementById('recent-alerts').innerHTML = alertsHtml;
                } catch (error) {
                    document.getElementById('recent-alerts').innerHTML = '<p>Error loading alerts</p>';
                }
            }

            // Load review queue
            async function loadReviewQueue() {
                try {
                    const queueHtml = `
                        <table>
                            <thead>
                                <tr>
                                    <th>Payment ID</th>
                                    <th>User</th>
                                    <th>Amount</th>
                                    <th>Risk Score</th>
                                    <th>Reason</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>abc123...</td>
                                    <td>jekopaul1</td>
                                    <td>$135.00</td>
                                    <td>0.75</td>
                                    <td>High velocity transactions</td>
                                    <td>2 hours ago</td>
                                    <td>
                                        <button class="btn btn-success">Approve</button>
                                        <button class="btn btn-danger">Reject</button>
                                    </td>
                                </tr>
                                <tr>
                                    <td>def456...</td>
                                    <td>user123</td>
                                    <td>$67.50</td>
                                    <td>0.65</td>
                                    <td>Unusual transaction time</td>
                                    <td>4 hours ago</td>
                                    <td>
                                        <button class="btn btn-success">Approve</button>
                                        <button class="btn btn-danger">Reject</button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `;
                    document.getElementById('review-queue').innerHTML = queueHtml;
                } catch (error) {
                    document.getElementById('review-queue').innerHTML = '<p>Error loading review queue</p>';
                }
            }

            // Load all data when page loads
            window.addEventListener('load', function() {
                loadStats();
                loadAlerts();
                loadReviewQueue();
            });
        </script>
    </body>
    </html>
    """
    
    return html_content

@app.get("/health")
async def health():
    """Health check"""
    return {"ok": True, "service": "fraud_admin_dashboard"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)