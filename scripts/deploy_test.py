#!/usr/bin/env python3
"""
Trinity Production Deployment Test Script

This script validates that the system is ready for production deployment by:
1. Testing server server health and API endpoints
2. Verifying client build process
3. Performing actual API call verification
4. Checking environment configurations
5. Validating Supabase connectivity

Run this script before any production deployment.
"""

import asyncio
import sys
import os
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class DeploymentTester:
    def __init__(self):
        self.test_results = []
        self.server_url = "http://localhost:8000"
        self.supabase_url = "https://stoigfjmmjetkphbpcis.supabase.co"
        self.start_time = datetime.now()

    def log_test(self, test_name, status, message=""):
        """Log test results with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "timestamp": timestamp
        }
        self.test_results.append(result)

        status_symbol = "✅" if status == "PASS" else "❌"
        print(f"{status_symbol} [{timestamp}] {test_name}: {message}")

    def test_environment_variables(self):
        """Verify all required environment variables are set"""
        test_name = "Environment Variables"

        # Check root .env
        env_path = project_root / ".env"
        if not env_path.exists():
            self.log_test(test_name, "FAIL", "Root .env file missing")
            return

        # Check key variables
        env_content = env_path.read_text()
        required_vars = [
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_KEY",
            "NVIDIA_API_KEY"
        ]

        missing_vars = []
        for var in required_vars:
            if f"{var}=" not in env_content:
                missing_vars.append(var)

        if missing_vars:
            self.log_test(test_name, "FAIL", f"Missing variables: {', '.join(missing_vars)}")
        else:
            self.log_test(test_name, "PASS", "All required variables present")

    def test_server_server(self):
        """Test if server API server is responsive"""
        test_name = "Backend Server"

        try:
            response = requests.get(f"{self.server_url}/docs", timeout=10)
            if response.status_code == 200:
                self.log_test(test_name, "PASS", "Backend server responsive")
            else:
                self.log_test(test_name, "FAIL", f"Status code: {response.status_code}")
        except Exception as e:
            self.log_test(test_name, "FAIL", f"Connection failed: {str(e)}")

    def test_api_endpoints(self):
        """Test key API endpoints"""
        test_name = "API Endpoints"
        endpoints_to_test = [
            ("/api/agents", "Agents endpoint"),
            ("/api/strategies", "Strategies endpoint"),
            ("/api/backtest", "Backtest endpoint")
        ]

        all_passed = True
        for endpoint, description in endpoints_to_test:
            try:
                response = requests.get(f"{self.server_url}{endpoint}", timeout=10)
                if response.status_code in [200, 401]:  # 401 is OK (auth required)
                    self.log_test(f"{test_name} - {description}", "PASS", "Endpoint responsive")
                else:
                    self.log_test(f"{test_name} - {description}", "FAIL", f"Status: {response.status_code}")
                    all_passed = False
            except Exception as e:
                self.log_test(f"{test_name} - {description}", "FAIL", f"Error: {str(e)}")
                all_passed = False

        if all_passed:
            self.log_test(test_name, "PASS", "All key endpoints responsive")

    def test_supabase_connectivity(self):
        """Test Supabase database connectivity"""
        test_name = "Supabase Connectivity"

        try:
            from dotenv import load_dotenv
            load_dotenv()

            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")

            if not supabase_url or not supabase_key:
                self.log_test(test_name, "FAIL", "Supabase credentials not found")
                return

            # Test auth endpoint
            response = requests.get(
                f"{supabase_url}/auth/v1/settings",
                headers={"Authorization": f"Bearer {supabase_key}"},
                timeout=10
            )

            if response.status_code == 200:
                self.log_test(test_name, "PASS", "Supabase connection successful")
            else:
                self.log_test(test_name, "FAIL", f"Auth failed: {response.status_code}")

        except Exception as e:
            self.log_test(test_name, "FAIL", f"Supabase test failed: {str(e)}")

    def test_client_build(self):
        """Test if client can be built successfully"""
        test_name = "Frontend Build"

        try:
            # Check if client directory exists
            client_dir = project_root / "client"
            if not client_dir.exists():
                self.log_test(test_name, "FAIL", "Frontend directory not found")
                return

            # Test npm install
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(client_dir),
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                self.log_test(test_name, "FAIL", f"npm install failed: {result.stderr[:200]}")
                return

            # Test build
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(client_dir),
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                self.log_test(test_name, "PASS", "Frontend build successful")
            else:
                self.log_test(test_name, "FAIL", f"Build failed: {result.stderr[:200]}")

        except Exception as e:
            self.log_test(test_name, "FAIL", f"Frontend build test failed: {str(e)}")

    def test_integration_tests(self):
        """Run integration tests to verify system functionality"""
        test_name = "Integration Tests"

        try:
            # Run server integration tests
            result = subprocess.run(
                ["python", "-m", "pytest", "server/ai_trading/tests/test_integration.py", "-v"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60
            )

            if "passed" in result.stdout.lower() and result.returncode == 0:
                self.log_test(test_name, "PASS", "Integration tests passed")
            else:
                self.log_test(test_name, "FAIL", f"Tests failed: {result.stderr[:200]}")

        except Exception as e:
            self.log_test(test_name, "FAIL", f"Integration test execution failed: {str(e)}")

    def generate_report(self):
        """Generate deployment readiness report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASS"])
        failed_tests = total_tests - passed_tests

        report = f"""
# Trinity Production Deployment Readiness Report

## Summary
- **Total Tests**: {total_tests}
- **Passed**: {passed_tests}
- **Failed**: {failed_tests}
- **Success Rate**: {passed_tests/total_tests*100:.1f}%
- **Test Duration**: {(datetime.now() - self.start_time).total_seconds():.1f}s

## Test Results
"""

        for result in self.test_results:
            status_symbol = "✅" if result["status"] == "PASS" else "❌"
            report += f"{status_symbol} **{result['test']}** - {result['message']} ({result['timestamp']})\n"

        # Deployment recommendation
        if failed_tests == 0:
            report += "\n## 🚀 DEPLOYMENT RECOMMENDATION: APPROVED"
            report += "\nAll critical tests passed. System is ready for production deployment."
        else:
            report += "\n## ⚠️ DEPLOYMENT RECOMMENDATION: HOLD"
            report += "\nCritical tests failed. Please fix issues before deployment."

        return report

    def run_all_tests(self):
        """Run all deployment tests"""
        print("🚀 Starting Trinity Production Deployment Tests...\n")

        # Run tests in order
        self.test_environment_variables()
        self.test_server_server()
        self.test_api_endpoints()
        self.test_supabase_connectivity()
        self.test_client_build()
        self.test_integration_tests()

        print("\n" + "="*60)
        report = self.generate_report()
        print(report)

        # Save report to file
        report_path = project_root / "docs" / "superpowers" / "progress" / "deployment-readiness.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)

        print(f"\n📊 Report saved to: {report_path}")

        return all(r["status"] == "PASS" for r in self.test_results)

async def main():
    """Main execution function"""
    tester = DeploymentTester()
    success = tester.run_all_tests()

    if success:
        print("\n🎉 All tests passed! System is ready for production deployment.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please fix issues before deployment.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())