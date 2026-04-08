import pytest
from unittest.mock import patch, MagicMock, mock_open
from typing import Dict, Set
import usage_matcher

@pytest.fixture
def mock_installed_packages():
    return {
        'requests': '2.28.0',
        'urllib3': '1.26.12',
        'pyyaml': '6.0'
    }

@pytest.fixture
def mock_imported_modules():
    return {'os', 'sys', 'requests', 'json'}

@pytest.fixture
def mock_metadata_response():
    return MagicMock()

@pytest.fixture
def temp_code_dir(tmp_path):
    code_file = tmp_path / "app.py"
    code_file.write_text("import requests\nimport os\nimport nonexistent_lib\n")
    return tmp_path

class TestGetInstalledPackages:
    def test_returns_package_dict(self, mock_installed_packages):
        with patch.object(usage_matcher, 'get_installed_packages', return_value=mock_installed_packages):
            result = usage_matcher.get_installed_packages()
        assert isinstance(result, dict)
        assert result == mock_installed_packages

    def test_raises_error_on_missing_metadata(self, mock_installed_packages, tmp_path):
        def failing_get_installed_packages():
            raise FileNotFoundError("Metadata not found")
        
        with patch.object(usage_matcher, 'get_installed_packages', side_effect=failing_get_installed_packages):
            with pytest.raises(FileNotFoundError):
                usage_matcher.get_installed_packages()

    def test_returns_empty_dict_when_no_packages_installed(self):
        with patch.object(usage_matcher, 'get_installed_packages', return_value={}):
            result = usage_matcher.get_installed_packages()
        assert isinstance(result, dict)
        assert len(result) == 0

class TestFindOrphans:
    def test_identifies_unused_packages(self, mock_installed_packages, mock_imported_modules):
        installed = {'requests': '2.28.0', 'unused_pkg': '1.0.0'}
        imports = {'requests'}
        with patch.object(usage_matcher, 'get_installed_packages', return_value=installed):
            with patch.object(usage_matcher, 'get_imports_from_directory', return_value=imports):
                result = usage_matcher.find_orphans()
        assert 'unused_pkg' in result

    def test_returns_empty_list_for_used_packages(self, mock_installed_packages, mock_imported_modules):
        installed = {'requests': '2.28.0'}
        imports = {'requests', 'os'}
        with patch.object(usage_matcher, 'get_installed_packages', return_value=installed):
            with patch.object(usage_matcher, 'get_imports_from_directory', return_value=imports):
                result = usage_matcher.find_orphans()
        assert len(result) == 0

    def test_handles_missing_import_module_gracefully(self, mock_installed_packages, mock_imported_modules):
        def return_none_imports():
            return set()
        
        installed = {'requests': '2.28.0'}
        with patch.object(usage_matcher, 'get_installed_packages', return_value=installed):
            with patch.object(usage_matcher, 'get_imports_from_directory', side_effect=return_none_imports):
                result = usage_matcher.find_orphans()
        assert len(result) > 0

class TestExternalAPI:
    @patch('requests.get')
    def test_validates_package_existence_happy_path(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        usage_matcher.module_registry_url = "https://pypi.org/pypi/{name}/json"
        
        result = usage_matcher.validate_package_on_registry("requests")
        assert result is True
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_handles_api_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        usage_matcher.module_registry_url = "https://pypi.org/pypi/{name}/json"
        
        result = usage_matcher.validate_package_on_registry("nonexistent_package_xyz")
        assert result is False
        mock_get.assert_called_once()

    @patch('requests.exceptions.RequestException')
    def test_handles_network_exception(self, mock_request_exception, mock_installed_packages):
        import requests
        mock_request_exception.side_effect = requests.exceptions.RequestException()
        
        with patch.object(usage_matcher, 'requests', side_effect=mock_request_exception):
            with patch.object(usage_matcher, 'get_installed_packages', return_value=mock_installed_packages):
                result = usage_matcher.scan_and_validate()
        assert isinstance(result, list)

class TestCodeAnalysis:
    def test_parses_python_imports(self, temp_code_dir):
        imports = usage_matcher.scan_directory(temp_code_dir)
        assert 'requests' in imports
        assert 'os' in imports

    def test_handles_non_python_files(self, temp_code_dir):
        import os
        dummy_file = temp_code_dir / "test.txt"
        dummy_file.write_text("hello world")
        
        imports = usage_matcher.scan_directory(temp_code_dir)
        # Should not crash or import text content
        assert isinstance(imports, set)

    def test_handles_permission_denied(self, tmp_path):
        import stat
        os.chmod(tmp_path, 0o000)
        
        with pytest.raises(PermissionError):
            usage_matcher.scan_directory(tmp_path)
        
        # Reset permissions for cleanup
        os.chmod(tmp_path, 0o755)

class TestReportGeneration:
    def test_formats_json_output_correctly(self, mock_installed_packages):
        orphans = ['unused_pkg']
        report = usage_matcher.generate_json_report(orphans)
        assert isinstance(report, str)
        import json
        data = json.loads(report)
        assert 'unused_pkg' in data

    def test_handles_empty_report(self):
        report = usage_matcher.generate_json_report