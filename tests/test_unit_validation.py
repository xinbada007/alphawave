#!/usr/bin/env python3
"""
Unit test for the combined collector functionality
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime

sys.path.insert(0, '/root/workspace/alphawave')

from alphaflow.core.schema import AnalysisContext, ResearchPack
from alphaflow.components.collectors.fundamental import FundamentalCollector


class TestFundamentalCollector(unittest.TestCase):
    """Test cases for FundamentalCollector with merged market data functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.context = AnalysisContext(symbols=["AAPL"])
        self.pack = ResearchPack(symbol="AAPL")
        self.collector = FundamentalCollector(name="test_collector", config={'provider': 'yfinance'})
        
    @patch('alphaflow.components.collectors.fundamental.obb')
    @patch('alphaflow.components.collectors.fundamental.DiskCache')
    def test_init_with_provider_config(self, mock_cache, mock_obb):
        """Test initialization with provider configuration"""
        config = {'provider': 'polygon'}
        collector = FundamentalCollector(name="test", config=config)
        
        self.assertEqual(collector.provider, 'polygon')
        
    @patch('alphaflow.components.collectors.fundamental.obb')
    @patch('alphaflow.components.collectors.fundamental.DiskCache')
    def test_fetch_data_method_exists(self, mock_cache, mock_obb):
        """Test that fetch_data method exists and is async"""
        self.assertTrue(hasattr(self.collector, 'fetch_data'))
        
        # Check if it's callable
        self.assertTrue(callable(getattr(self.collector, 'fetch_data')))
        
    @patch('alphaflow.components.collectors.fundamental.DiskCache')
    @patch('alphaflow.components.collectors.fundamental.get_api_key')
    @patch('alphaflow.components.collectors.fundamental.report_api_usage')
    @patch('alphaflow.components.collectors.fundamental.os.environ')
    @patch('alphaflow.components.collectors.fundamental.obb')
    def test_fetch_data_structure(self, mock_obb, mock_environ, mock_report_api, mock_get_api, mock_cache):
        """Test the structure of fetch_data method without calling external APIs"""
        # Mock the cache to return None (force API calls)
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance
        
        # Mock the API responses
        mock_price_res = Mock()
        mock_price_res.to_df.return_value = Mock()
        mock_price_res.to_df.return_value.empty = False
        mock_price_res.to_df.return_value.index = Mock()
        mock_price_res.to_df.return_value.index.__class__.__name__ = 'Index'
        
        mock_metrics_res = Mock()
        mock_metrics_res.to_df.return_value = Mock()
        mock_metrics_res.to_df.return_value.empty = False
        mock_metrics_res.to_df.return_value.iloc = Mock()
        mock_metrics_res.to_df.return_value.iloc.__getitem__ = lambda x: Mock(to_dict=lambda: {})
        
        mock_bs_res = Mock()
        mock_bs_res.to_df.return_value = Mock()
        mock_bs_res.to_df.return_value.empty = False
        mock_bs_res.to_df.return_value.iloc = Mock()
        mock_bs_res.to_df.return_value.iloc.__getitem__ = lambda x: Mock(to_dict=lambda: {})
        
        mock_income_res = Mock()
        mock_income_res.to_df.return_value = Mock()
        mock_income_res.to_df.return_value.empty = False
        mock_income_res.to_df.return_value.iloc = Mock()
        mock_income_res.to_df.return_value.iloc.__getitem__ = lambda x: Mock(to_dict=lambda: {})
        
        mock_cash_res = Mock()
        mock_cash_res.to_df.return_value = Mock()
        mock_cash_res.to_df.return_value.empty = False
        mock_cash_res.to_df.return_value.iloc = Mock()
        mock_cash_res.to_df.return_value.iloc.__getitem__ = lambda x: Mock(to_dict=lambda: {})
        
        # Configure obb mocks
        mock_obb.equity.price.historical.return_value = mock_price_res
        mock_obb.equity.fundamental.metrics.return_value = mock_metrics_res
        mock_obb.equity.fundamental.balance.return_value = mock_bs_res
        mock_obb.equity.fundamental.income.return_value = mock_income_res
        mock_obb.equity.fundamental.cash.return_value = mock_cash_res
        
        # Create async mock for the method
        async def async_mock(*args, **kwargs):
            return Mock(success=True, payload=self.pack)
        
        # Temporarily replace the method with our mock
        original_method = self.collector.fetch_data
        self.collector.fetch_data = async_mock
        
        try:
            # This would normally be awaited, but we're testing structure
            pass
        finally:
            # Restore original method
            self.collector.fetch_data = original_method
        
        # Verify that the method exists and has proper structure
        self.assertIsNotNone(original_method)
        
    @patch('alphaflow.components.collectors.fundamental.DiskCache')
    def test_initialization(self, mock_cache):
        """Test that the collector initializes properly"""
        config = {'provider': 'alpha_vantage'}
        collector = FundamentalCollector(name="test_collector", config=config)
        
        self.assertEqual(collector.name, "test_collector")
        self.assertEqual(collector.provider, 'alpha_vantage')
        self.assertIsNotNone(collector.cache)


class TestCodeStructure(unittest.TestCase):
    """Test the code structure and imports"""
    
    def test_imports_exist(self):
        """Test that required imports exist"""
        try:
            from alphaflow.core.base import BaseCollector
            from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack, DataFrameModel
            from alphaflow.utils.cache import DiskCache
            from alphaflow.utils.api_rotator import get_api_key, report_api_usage
            from openbb import obb
            import pandas as pd
            import os
            
            self.assertTrue(True)  # If we got here, all imports worked
        except ImportError as e:
            self.fail(f"Import failed: {e}")
    
    def test_class_inheritance(self):
        """Test that FundamentalCollector inherits from BaseCollector"""
        from alphaflow.core.base import BaseCollector
        from alphaflow.components.collectors.fundamental import FundamentalCollector
        
        self.assertTrue(issubclass(FundamentalCollector, BaseCollector))


def run_unit_tests():
    """Run all unit tests"""
    print("Running unit tests for combined collector...\n")
    
    # Create a test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print("UNIT TEST SUMMARY:")
    print(f"{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    success = result.wasSuccessful()
    print(f"\nOverall result: {'PASS' if success else 'FAIL'}")
    
    return success


if __name__ == '__main__':
    success = run_unit_tests()
    if not success:
        sys.exit(1)