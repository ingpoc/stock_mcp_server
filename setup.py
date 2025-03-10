from setuptools import setup, find_packages

setup(
    name="stock_mcp_server",
    version="0.1.0",
    description="MCP server for stock analysis application",
    packages=find_packages(),
    install_requires=[
        "mcp-python>=0.0.6",
        "websockets>=10.0",
        "requests>=2.28.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "stock-mcp-server=stock_mcp_server.server:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
    ],
) 