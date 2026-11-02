import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('oss_upload',Path(__file__).resolve().parents[1]/'scripts/deploy_aliyun_oss.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class AliyunUploadTests(unittest.TestCase):
    def test_repository_root_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):module.public_files(Path(folder))
    def test_only_public_site_is_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();(root/'index.html').write_text('<html/>');(root/'data/dashboard.json').write_text('{}')
            self.assertEqual(len(module.public_files(root)),2)
            (root/'.nojekyll').write_text('');self.assertEqual(len(module.public_files(root)),3)
            (root/'.env').write_text('fixture only')
            with self.assertRaises(ValueError):module.public_files(root)
    def test_private_subscription_list_cannot_be_uploaded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();(root/'index.html').write_text('<html/>');(root/'data/dashboard.json').write_text('{}');(root/'data/subscriber_list.json').write_text('[]')
            with self.assertRaises(ValueError):module.public_files(root)
if __name__=='__main__':unittest.main()
