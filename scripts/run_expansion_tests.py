"""Run the bounded fulltext regression suite and retain an auditable result."""
import argparse, json, sys, unittest
from pathlib import Path
import fulltext_pilot as p

parser = argparse.ArgumentParser()
parser.add_argument('--tests', default='tests')
parser.add_argument('--output', default='analysis/global_expansion_20261106/test_results.json')
args = parser.parse_args()
suite = unittest.TestSuite()
for pattern in ['test_fulltext*.py', 'test_bulk_fulltext.py', 'test_public_fulltext_library.py',
                'test_governance_taxonomy_v2.py', 'test_expansion_quality.py', 'test_global_postvalidation.py']:
    suite.addTests(unittest.defaultTestLoader.discover(args.tests, pattern=pattern))
result = unittest.TextTestRunner(verbosity=1).run(suite)
record = {'at': p.stamp(), 'tests_run': result.testsRun, 'failures': len(result.failures),
          'errors': len(result.errors), 'skipped': len(result.skipped), 'success': result.wasSuccessful()}
p.dump(Path(args.output), record)
print(json.dumps(record))
sys.exit(0 if result.wasSuccessful() else 1)
