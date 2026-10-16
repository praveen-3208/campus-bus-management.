"""
Automated Backend & Web Route Verification Suite
"""
import unittest
import json
import time
from app import app
from database import init_db, seed_sample_data

class BusGateSystemTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        init_db(seed_if_empty=True)

    def test_pages_render(self):
        """Verify all 6 HTML pages render with status 200."""
        routes = ['/', '/dashboard', '/buses', '/monitoring', '/camera', '/history', '/settings']
        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, f"Route {route} failed with {response.status_code}")
            self.assertIn(b"Campus Gate", response.data)

    def test_status_endpoint(self):
        """Verify /api/status returns proper counts and hardware states."""
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('counts', data)
        self.assertIn('hardware', data)
        self.assertIn('gate_sensor', data)
        self.assertGreater(data['counts']['total_buses'], 0)

    def test_bus_crud(self):
        """Test adding, fetching, updating, and deleting a bus."""
        # 1. Add bus
        new_bus = {
            'bus_id': 'TEST-99',
            'registration_no': 'KA-01-TEST-9999',
            'route_name': 'Test Route 99',
            'driver_name': 'Test Driver',
            'driver_contact': '+91 90000 00000',
            'status': 'Inside'
        }
        res = self.client.post('/api/buses', json=new_bus)
        self.assertEqual(res.status_code, 201)

        # 2. List buses and find it
        res = self.client.get('/api/buses?q=TEST-99')
        buses = res.get_json()
        self.assertEqual(len(buses), 1)
        bus_pk = buses[0]['id']

        # 3. Update bus
        res = self.client.put(f'/api/buses/{bus_pk}', json={
            'registration_no': 'KA-01-TEST-9999',
            'route_name': 'Updated Test Route',
            'driver_name': 'Updated Driver',
            'driver_contact': '+91 91111 11111',
            'status': 'Outside'
        })
        self.assertEqual(res.status_code, 200)

        # 4. Set as active
        res = self.client.post(f'/api/buses/{bus_pk}/set-active')
        self.assertEqual(res.status_code, 200)

        # 5. Delete bus
        res = self.client.delete(f'/api/buses/{bus_pk}')
        self.assertEqual(res.status_code, 200)

    def test_sensor_direction_inference(self):
        """Test that S1 then S2 detects ENTRY, and cooldown prevents duplicates."""
        # Pulse S1 (Outer)
        res1 = self.client.post('/api/sensor-event', json={
            'sensor': 's1',
            'distance': 35.0,
            'device_id': 'TEST-ESP32'
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertEqual(data1['status'], 'pending')

        # Pulse S2 (Inner) within transition window -> should detect ENTRY!
        res2 = self.client.post('/api/sensor-event', json={
            'sensor': 's2',
            'distance': 30.0,
            'device_id': 'TEST-ESP32'
        })
        self.assertEqual(res2.status_code, 201)
        data2 = res2.get_json()
        self.assertEqual(data2['direction'], 'ENTRY')

        # Immediately pulse again -> should be debounced!
        res3 = self.client.post('/api/sensor-event', json={
            'sensor': 's1',
            'distance': 30.0,
            'device_id': 'TEST-ESP32'
        })
        self.assertEqual(res3.status_code, 200)
        data3 = res3.get_json()
        self.assertEqual(data3['status'], 'debounced')

    def test_events_export_csv(self):
        """Verify CSV export returns valid CSV content."""
        res = self.client.get('/api/events/export')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Event ID,Bus ID,Registration No", res.data)

    def test_camera_diagnostics(self):
        """Verify camera test handles unreachable URL gracefully without false positives."""
        res = self.client.post('/api/camera/test', json={'camera_url': 'http://127.0.0.1:59999'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data['connected'])
        self.assertIn('Disconnected', data['status'].capitalize())

if __name__ == '__main__':
    unittest.main()
