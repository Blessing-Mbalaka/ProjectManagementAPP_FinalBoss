#!/usr/bin/env python
"""
Financial Dashboard Test Runner
Simple script to run the financial dashboard tests

Usage:
    python run_financial_tests.py [--verbose] [--specific-test TEST_NAME]
"""

import os
import sys
import django
import argparse

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from django.core.management import call_command
from django.test.utils import get_runner
from django.conf import settings


def run_tests(verbosity=1, test_label=None):
    """
    Run the financial dashboard tests
    
    Args:
        verbosity: Test output verbosity level (0, 1, or 2)
        test_label: Specific test to run (default: all financial tests)
    """
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=verbosity, interactive=True, keepdb=False)
    
    test_module = 'adminpanel.tests.FinancialDashboardTest'
    if test_label:
        test_module = f'{test_module}.{test_label}'
    
    print(f"\n{'='*70}")
    print(f"Running Financial Dashboard Tests")
    print(f"{'='*70}\n")
    
    failures = test_runner.run_tests([test_module])
    
    return failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Financial Dashboard Tests')
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=1,
        help='Increase output verbosity (can use multiple times)'
    )
    parser.add_argument(
        '--test', '-t',
        type=str,
        help='Run specific test class or method (e.g., FinancialDashboardTestData.test_finance_page_loads)'
    )
    
    args = parser.parse_args()
    
    sys.exit(bool(run_tests(verbosity=args.verbose, test_label=args.test)))
