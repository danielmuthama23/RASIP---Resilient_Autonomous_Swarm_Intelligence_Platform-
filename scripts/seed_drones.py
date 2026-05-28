import json

DRONE_COUNT = 20

def make_drone(idx):
    return {
        'id': f'DR-{idx+1:02d}',
        'lat': -1.2921,
        'lon': 36.8219,
        'battery': 100,
        'signal': 100,
    }

if __name__ == '__main__':
    data = [make_drone(i) for i in range(DRONE_COUNT)]
    print(json.dumps(data, indent=2))
