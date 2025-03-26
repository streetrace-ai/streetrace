import os
import codecs

def write_file(file_path, content, root_path=None, encoding='utf-8', binary_mode=False):
    """
    Securely write content to a file, ensuring the path is within the allowed root path.
    
    Args:
        file_path (str): Path to the file to write. Can be relative or absolute.
        content (str or bytes): Content to write to the file.
        root_path (str, optional): Root path that restricts access. If None, uses current directory.
            The file_path must be within this root_path for security.
        encoding (str, optional): Text encoding to use when writing text. Defaults to 'utf-8'.
            This is ignored if binary_mode is True.
        binary_mode (bool, optional): If True, write the file in binary mode. Defaults to False.
            In binary mode, content must be bytes.
    
    Returns:
        str: Path of the written file
        
    Raises:
        ValueError: If the file path is outside the allowed root path
        TypeError: If content type doesn't match the mode (str for text, bytes for binary)
        IOError: If there are issues writing the file
        OSError: If directory creation fails
    """
    # Default root_path to current directory if not specified
    if root_path is None:
        root_path = os.getcwd()
    
    # Get absolute paths for security comparison
    abs_root_path = os.path.abspath(os.path.normpath(root_path))
    abs_file_path = os.path.abspath(os.path.normpath(file_path))
    
    # Security check: ensure the file path is within the root path
    if not abs_file_path.startswith(abs_root_path):
        raise ValueError(f"Security error: Requested file path '{file_path}' is outside the allowed root path.")
    
    # Check content type
    if binary_mode and not isinstance(content, bytes):
        raise TypeError("Content must be bytes when binary_mode is True")
    if not binary_mode and not isinstance(content, str):
        raise TypeError("Content must be str when binary_mode is False")
    
    # Create directory if it doesn't exist
    directory = os.path.dirname(abs_file_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create directory '{directory}': {str(e)}")
    
    # Write the content to the file
    try:
        if binary_mode:
            with open(abs_file_path, 'wb') as f:
                f.write(content)
        else:
            with codecs.open(abs_file_path, 'w', encoding=encoding) as f:
                f.write(content)
        return file_path
    except IOError as e:
        raise IOError(f"Error writing to file '{file_path}': {str(e)}") 