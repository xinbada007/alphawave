#!/usr/bin/env python3
"""
Integration test for the combined collector
"""

import sys
import os
import importlib.util

def test_integration():
    """Test that the module can be properly integrated"""
    print("Testing integration of combined collector...\n")
    
    # Add the workspace to the path
    sys.path.insert(0, '/root/workspace/alphawave')
    
    try:
        # Test 1: Import the module
        print("1. Testing module import...")
        spec = importlib.util.spec_from_file_location(
            "fundamental", 
            "/root/workspace/alphawave/alphaflow/components/collectors/fundamental.py"
        )
        fundamental_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fundamental_module)
        print("   ✓ Module imported successfully")
        
        # Test 2: Access the class
        print("2. Testing class access...")
        FundamentalCollector = getattr(fundamental_module, 'FundamentalCollector')
        print("   ✓ FundamentalCollector class accessible")
        
        # Test 3: Check class attributes and methods
        print("3. Testing class structure...")
        methods = [method for method in dir(FundamentalCollector) if not method.startswith('_')]
        print(f"   ✓ Found methods: {methods}")
        
        # Check for required methods
        required_methods = ['__init__', 'fetch_data']
        missing_methods = [m for m in required_methods if m not in methods]
        if missing_methods:
            print(f"   ✗ Missing required methods: {missing_methods}")
            return False
        else:
            print("   ✓ All required methods present")
        
        # Test 4: Create an instance
        print("4. Testing instance creation...")
        collector_instance = FundamentalCollector(name="integration_test", config={'provider': 'yfinance'})
        print("   ✓ Instance created successfully")
        
        # Test 5: Check instance attributes
        print("5. Testing instance attributes...")
        attrs = ['name', 'cache', 'provider']
        for attr in attrs:
            if hasattr(collector_instance, attr):
                print(f"   ✓ Attribute '{attr}' exists: {getattr(collector_instance, attr)}")
            else:
                print(f"   ✗ Attribute '{attr}' missing")
                return False
        
        # Test 6: Check inheritance
        print("6. Testing inheritance...")
        from alphaflow.core.base import BaseCollector
        if isinstance(collector_instance, BaseCollector):
            print("   ✓ Properly inherits from BaseCollector")
        else:
            print("   ✗ Does not inherit from BaseCollector")
            return False
        
        print("\n✓ All integration tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schema_compatibility():
    """Test compatibility with the expected schemas"""
    print("\nTesting schema compatibility...\n")
    
    try:
        # Add the workspace to the path
        sys.path.insert(0, '/root/workspace/alphawave')
        
        # Test importing required schemas
        print("1. Testing schema imports...")
        from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack, DataFrameModel
        print("   ✓ Schema classes imported successfully")
        
        # Test creating instances
        print("2. Testing schema instance creation...")
        context = AnalysisContext(symbols=["AAPL"])
        pack = ResearchPack(symbol="AAPL")
        print(f"   ✓ AnalysisContext created: {context.symbols}")
        print(f"   ✓ ResearchPack created: {pack.symbol}")
        
        # Test ComponentOutput
        output = ComponentOutput(success=True, payload=pack)
        print(f"   ✓ ComponentOutput created: {output.success}")
        
        print("\n✓ All schema compatibility tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Schema compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("="*60)
    print("INTEGRATION TESTS FOR COMBINED COLLECTOR")
    print("="*60)
    
    test_results = []
    
    # Run integration test
    print("\nRUNNING INTEGRATION TESTS...")
    result1 = test_integration()
    test_results.append(("Integration Tests", result1))
    
    # Run schema compatibility test
    print("\nRUNNING SCHEMA COMPATIBILITY TESTS...")
    result2 = test_schema_compatibility()
    test_results.append(("Schema Compatibility", result2))
    
    # Print summary
    print("\n" + "="*60)
    print("INTEGRATION TEST SUMMARY:")
    print("="*60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print(f"\nOverall result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)