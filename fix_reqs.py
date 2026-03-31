import re
import codecs

def fix_requirements():
    with codecs.open('requirements.txt', 'r', 'utf-8') as f:
        content = f.read()

    # Reconstruct the original bytes that caused this
    bytes_content = content.encode('utf-16-le')
    
    # Just extract all ascii strings that look like package==version
    ascii_text = bytes_content.replace(b'\x00', b'').decode('ascii', errors='ignore')
    
    # Find all packages requirements
    # Things like: aiofiles==23.2.1 or django>=5.0.0 or aiohttp
    packages = re.findall(r'[a-zA-Z0-9\-_]+(?:[=><!~]+[a-zA-Z0-9\-_\.]+|)', ascii_text)
    
    # Filter out empty or obviously wrong ones
    valid_packages = []
    for p in packages:
        if len(p) > 2 and '===' not in p:
            valid_packages.append(p)
            
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        for p in valid_packages:
            f.write(p + '\n')

if __name__ == '__main__':
    fix_requirements()
