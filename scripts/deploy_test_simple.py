#!/usr/bin/env python3
"""
Trinity Production Deployment Test Script (Simple Version)

This script validates deployment readiness with minimal dependencies.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

class SimpleDeploymentTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_results = []
        self.start_time = datetime.now()

    def log_test(self, test_name, status, message=""):
        """Log test results"""
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

    def test_file_existence(self):
        """Verify critical files exist"""
        required_files = [
            ("CLAUDE.md", "Project instructions"),
            ("PROJECT.md", "Project specification"),
            ("run", "Project runner script"),
            (".env", "Environment configuration"),
            ("api/main.py", "Backend server entry point"),
            ("front/package.json", "Frontend package configuration"),
            ("ai_trading/core/strategy_loader.py", "Strategy loader"),
            ("ai_trading/tests/test_integration.py", "Integration tests")
        ]

        all_exist = True
        for file_path, description in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.log_test(f"File: {description}", "PASS", f"{file_path} exists")
            else:
                self.log_test(f"File: {description}", "FAIL", f"{file_path} missing")
                all_exist = False

        return all_exist

    def test_env_variables(self):
        """Check if environment files have required variables"""
        test_name = "Environment Variables"

        env_path = self.project_root / ".env"
        if not env_path.exists():
            self.log_test(test_name, "FAIL", "Root .env file missing")
            return False

        env_content = env_path.read_text()
        required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]

        missing = []
        for var in required_vars:
            if f"{var}=" not in env_content:
                missing.append(var)

        if missing:
            self.log_test(test_name, "FAIL", f"Missing: {', '.join(missing)}")
            return False
        else:
            self.log_test(test_name, "PASS", "All required variables present")
            return True

    def test_python_modules(self):
        """Test Python module imports"""
        test_name = "Python Modules"

        try:
            # Add project root to path
            sys.path.insert(0, str(self.project_root))

            # Test core imports
            imports_to_test = [
                "ai_trading.core.strategy_loader",
                "ai_trading.core.backtest_manager",
                "api.services.supabase_client"
            ]

            all_imported = True
            for module_path in imports_to_test:
                try:
                    __import__(module_path)
                    self.log_test(f"Import: {module_path}", "PASS", "Module loads successfully")
                except ImportError as e:
                    self.log_test(f"Import: {module_path}", "FAIL", f"Import error: {str(e)}")
                    all_imported = False

            if all_imported:
                self.log_test(test_name, "PASS", "All core modules import successfully")
            else:
                self.log_test(test_name, "FAIL", "Some modules failed to import")

        except Exception as e:
            self.log_test(test_name, "FAIL", f"Import test failed: {str(e)}")

    def test_run_script(self):
        """Test the run script syntax"""
        test_name = "Run Script"

        script_path = self.project_root / "run"
        if not script_path.exists():
            self.log_test(test_name, "FAIL", "Run script missing")
            return False

        # Check if executable
        if not os.access(str(script_path), os.X_OK):
            self.log_test(test_name, "FAIL", "Run script not executable")
            return False

        # Check syntax
        try:
            result = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_test(test_name, "PASS", "Run script syntax valid")
                return True
            else:
                self.log_test(test_name, "FAIL", f"Syntax error: {result.stderr}")
                return False
        except Exception as e:
            self.log_test(test_name, "FAIL", f"Syntax check failed: {str(e)}")
            return False

    def test_integration_tests(self):
        """Run integration tests"""
        test_name = "Integration Tests"

        test_file = self.project_root / "ai_trading" / "tests" / "test_integration.py"
        if not test_file.exists():
            self.log_test(test_name, "FAIL", "Integration test file missing")
            return False

        try:
            # Set Python path for imports
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.project_root)

            result = subprocess.run(
                ["python3", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )

            if result.returncode == 0:
                self.log_test(test_name, "PASS", "Integration tests passed")
                return True
            else:
                # Check if tests actually ran
                if "test session starts" in result.stdout:
                    self.log_test(test_name, "FAIL", f"Tests failed: {result.stderr[:200]}")
                else:
                    self.log_test(test_name, "FAIL", "Tests could not run")
                return False

        except subprocess.TimeoutExpired:
            self.log_test(test_name, "FAIL", "Test execution timed out")
            return False
        except Exception as e:
            self.log_test(test_name, "FAIL", f"Test execution error: {str(e)}")
            return False

    def test_frontend_build(self):
        """Test frontend build readiness"""
        test_name = "Frontend Build"

        frontend_dir = self.project_root / "front"
        package_json = frontend_dir / "package.json"

        if not package_json.exists():
            self.log_test(test_name, "FAIL", "Frontend package.json missing")
            return False

        # Check if build script exists
        try:
            import json
            with open(package_json, 'r') as f:
                package_data = json.load(f)

            if "scripts" in package_data and "build" in package_data["scripts"]:
                self.log_test(test_name, "PASS", "Frontend build script available")
                return True
            else:
                self.log_test(test_name, "FAIL", "No build script in package.json")
                return False

        except Exception as e:
            self.log_test(test_name, "FAIL", f"Package.json error: {str(e)}")
            return False

    def generate_report(self):
        """Generate deployment readiness report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASS"])
        failed_tests = total_tests - passed_tests

        report = f"""
# Trinity Production Deployment Readiness Report (Simple Version)

## Summary
- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Total Tests**: {total_tests}
- **Passed**: {passed_tests}
- **Failed**: {failed_tests}
- **Success Rate**: {(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%
- **Test Duration**: {(datetime.now() - self.start_time).total_seconds():.1f}s

## Critical Tests
"""

        # Group by test category
        critical_tests = []
        file_tests = []
        other_tests = []

        for result in self.test_results:
            if result["test"].startswith("File:"):
                file_tests.append(result)
            elif result["test"] in ["Environment Variables", "Python Modules", "Integration Tests", "Frontend Build", "Run Script"]:
                critical_tests.append(result)
            else:
                other_tests.append(result)

        report += "\n### Critical Functionality\n"
        for result in critical_tests:
            status_symbol = "✅" if result["status"] == "PASS" else "❌"
            report += f"{status_symbol} **{result['test']}** - {result['message']}\n"

        report += "\n### File System Check\n"
        for result in file_tests:
            status_symbol = "✅" if result["status"] == "PASS" else "❌"
            report += f"{status_symbol} {result['test']}\n"

        # Deployment recommendation
        critical_passed = len([r for r in critical_tests if r["status"] == "PASS"])
        total_critical = len(critical_tests)

        if total_critical > 0 and critical_passed == total_critical:
            report += "\n## 🚀 DEPLOYMENT RECOMMENDATION: APPROVED"
            report += "\nAll critical tests passed. System is ready for production deployment."
        else:
            report += "\n## ⚠️ DEPLOYMENT RECOMMENDATION: HOLD"
            report += f"\nCritical tests failed ({critical_passed}/{total_critical} passed). Please fix issues before deployment."

        return report

    def run_all_tests(self):
        """Run all deployment tests"""
        print("🚀 Starting Trinity Production Deployment Tests (Simple)...\n")

        # Run tests
        self.test_file_existence()
        self.test_env_variables()
        self.test_python_modules()
        self.test_run_script()
        self.test_integration_tests()
        self.test_frontend_build()

        print("\n" + "="*60)
        report = self.generate_report()
        print(report)

        # Save report to file
        docs_dir = self.project_root / "docs" / "superpowers" / "progress"
        docs_dir.mkdir(parents=True, exist_ok=True)
        report_path = docs_dir / "deployment-readiness.md"

        report_path.write_text(report)
        print(f"\n📊 Report saved to: {report_path}")

        # Return success if all critical tests passed
        critical_tests = [r for r in self.test_results if r["test"] in [
            "Environment Variables", "Python Modules", "Integration Tests", "Frontend Build", "Run Script"
        ]]

        return all(r["status"] == "PASS" for r in critical_tests)

def main():
    """Main execution function"""
    tester = SimpleDeploymentTester()
    success = tester.run_all_tests()

    if success:
        print("\n🎉 All critical tests passed! System is ready for production deployment.")
        return 0
    else:
        print("\n❌ Some critical tests failed. Please fix issues before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())