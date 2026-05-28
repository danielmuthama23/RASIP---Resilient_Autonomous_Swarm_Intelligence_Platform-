import asyncio
import random
import json

async def main():
    while True:
        frame = {
            'id': f'DR-{random.randint(1,20):02d}',
            'battery': max(0, 100 - random.random() * 20),
            'signal': max(0, 100 - random.random() * 10),
            'ai_conf': max(0, min(100, 90 + random.gauss(0, 5))),
        }
        print(json.dumps(frame))
        await asyncio.sleep(1.0)

if __name__ == '__main__':
    asyncio.run(main())
