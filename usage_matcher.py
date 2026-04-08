import os
import ast
import pkg_resources

def get_installed_packages():
    """
    Returns a dictionary of installed packages with their metadata.
    """
    installed = {}
    for dist in pkg_resources.working_set:
        try:
            installed[dist.project_name] = {
                'version': dist.version,
                'metadata': dist.get_metadata('METADATA'),
                'location': dist.location
            }
        except (OSError, KeyError):
            raise RuntimeError(f"Missing metadata for package: {dist.project_name}")
    return installed


def get_imports_from_directory(directory_path):
    """
    Scans a directory for Python files and extracts package import names.
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        List of package names found in imports
        
    Raises:
        OSError: If the directory cannot be accessed
    """
    import_names = set()
    try:
        if not os.path.isdir(directory_path):
            raise OSError(f"Directory not found: {directory_path}")
            
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    import_names.add(alias.name.split('.')[0])
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    import_names.add(node.module.split('.')[0])
                    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                        continue
    except OSError:
        raise
    return list(import_names)


def find_orphans(dependencies, installed_packages, directory_path=None):
    """
    Identifies packages that are installed but not in the dependencies list.
    
    Args:
        dependencies: List of package names that are required
        installed_packages: Dictionary of installed packages
        directory_path: Optional path to scan for imports if dependencies not provided
        
    Returns:
        List of package names that are unused/orphan packages
    """
    if dependencies is None:
        dependencies = []
    elif not isinstance(dependencies, list):
        dependencies = list(dependencies)
        
    # If dependencies are empty and directory_path provided, scan for imports
    # This allows get_imports_from_directory to be mocked for testing
    if not dependencies and directory_path:
        try:
            dependencies = get_imports_from_directory(directory_path)
        except Exception:
            dependencies = []

    used_packages = set(dependencies)
    installed_package_names = set(installed_packages.keys())
    
    unused_packages = installed_package_names - used_packages
    return list(unused_packages)