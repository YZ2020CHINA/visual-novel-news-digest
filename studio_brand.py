"""Self-contained studio signature, also used to update archived mastheads."""
import base64
from pathlib import Path


def studio_brand_html():
    image = base64.b64encode((Path(__file__).parent / 'static/images/studio-logo.png').read_bytes()).decode('ascii')
    return f'''<div class="studio-brand">
                <a class="studio-logo-link" href="https://x.com/johnvauk" target="_blank" rel="noopener noreferrer" aria-label="自动代谢工作室 · 在 X 上关注">
                    <img class="studio-logo" src="data:image/png;base64,{image}" alt="自动代谢工作室 Automatic Metabolism Studio" width="960" height="467">
                </a>
                <a class="studio-social" href="https://x.com/johnvauk" target="_blank" rel="noopener noreferrer"><span class="studio-social-label">工作室动态 / X</span><span class="studio-handle">@johnvauk <span aria-hidden="true">↗</span></span></a>
            </div>'''
