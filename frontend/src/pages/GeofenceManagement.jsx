import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Circle, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin, Plus, Trash2, Save, RefreshCw } from 'lucide-react';

const API_URL = 'http://localhost:8000/api';

// Helper component to handle map clicks for adding new geofences
function LocationSelector({ onLocationSelect }) {
  useMapEvents({
    click(e) {
      onLocationSelect(e.latlng);
    },
  });
  return null;
}

export default function GeofenceManagement() {
  const [geofences, setGeofences] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newFence, setNewFence] = useState(null); // { lat, lng, name, radius }
  const [isAdding, setIsAdding] = useState(false);

  // Hardcoded token/role for admin - assuming auth context provides this in a real app
  // For this prototype, we'll fetch directly (ensure backend doesn't strictly block without token if testing locally, or pass valid auth)

  const fetchGeofences = async () => {
    setLoading(true);
    try {
      // In a real app, include Authorization headers
      const res = await fetch(`${API_URL}/geofence`, {
        // headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      if (res.ok) {
        const data = await res.json();
        setGeofences(data);
      }
    } catch (err) {
      console.error('Failed to fetch geofences', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchGeofences();
  }, []);

  const handleMapClick = (latlng) => {
    if (isAdding) {
      setNewFence({
        name: 'New Zone',
        latitude: latlng.lat,
        longitude: latlng.lng,
        radius_meters: 100,
        is_active: true
      });
    }
  };

  const handleSaveNew = async () => {
    if (!newFence) return;
    try {
      const res = await fetch(`${API_URL}/geofence`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Authorization: `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(newFence)
      });
      if (res.ok) {
        setIsAdding(false);
        setNewFence(null);
        fetchGeofences();
      }
    } catch (err) {
      console.error('Failed to save geofence', err);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this geofence?')) return;
    try {
      const res = await fetch(`${API_URL}/geofence/${id}`, {
        method: 'DELETE',
        // headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      if (res.ok) {
        fetchGeofences();
      }
    } catch (err) {
      console.error('Failed to delete geofence', err);
    }
  };

  return (
    <div className="min-h-screen bg-dark-950 text-white p-6 md:p-10">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400 flex items-center gap-3">
              <MapPin className="text-blue-400" />
              Geofence Management
            </h1>
            <p className="text-dark-400 mt-2">Define allowed location zones for student check-ins.</p>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={fetchGeofences}
              className="btn-secondary flex items-center gap-2 px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 transition"
            >
              <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
            <button 
              onClick={() => setIsAdding(!isAdding)}
              className={`btn-primary flex items-center gap-2 px-4 py-2 rounded-xl transition ${isAdding ? 'bg-rose-500 hover:bg-rose-600' : 'bg-emerald-500 hover:bg-emerald-600'}`}
            >
              {isAdding ? 'Cancel' : <><Plus size={18} /> Add Zone</>}
            </button>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Map Section */}
          <div className="lg:col-span-2 bg-dark-900 border border-dark-800 rounded-2xl overflow-hidden h-[600px] relative shadow-lg">
            {isAdding && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] bg-dark-900/90 backdrop-blur border border-emerald-500/30 text-emerald-400 px-6 py-3 rounded-full shadow-lg flex items-center gap-2 animate-bounce">
                <MapPin size={18} />
                Click anywhere on the map to place a new geofence
              </div>
            )}
            
            <MapContainer 
              center={[37.7749, -122.4194]} // Default center (San Francisco or use campus coordinates)
              zoom={13} 
              style={{ height: '100%', width: '100%' }}
              className="z-0"
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; <a href="https://carto.com/">CARTO</a>'
              />
              <LocationSelector onLocationSelect={handleMapClick} />
              
              {/* Existing Geofences */}
              {geofences.map(geo => (
                <Circle 
                  key={geo.id}
                  center={[geo.latitude, geo.longitude]}
                  radius={geo.radius_meters}
                  pathOptions={{ color: geo.is_active ? '#10b981' : '#6b7280', fillColor: geo.is_active ? '#10b981' : '#6b7280', fillOpacity: 0.2 }}
                />
              ))}

              {/* New Geofence Preview */}
              {newFence && (
                <Circle 
                  center={[newFence.latitude, newFence.longitude]}
                  radius={newFence.radius_meters}
                  pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.4, dashArray: '5, 5' }}
                />
              )}
            </MapContainer>
          </div>

          {/* Sidebar Editor */}
          <div className="space-y-6">
            
            {/* New Zone Editor */}
            {newFence && (
              <div className="bg-dark-900 border border-blue-500/30 rounded-2xl p-6 shadow-glow">
                <h2 className="text-xl font-semibold mb-4 text-blue-400 flex items-center gap-2">
                  <Plus size={20} />
                  Configure New Zone
                </h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">Zone Name</label>
                    <input 
                      type="text" 
                      value={newFence.name}
                      onChange={(e) => setNewFence({...newFence, name: e.target.value})}
                      className="w-full bg-dark-950 border border-dark-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">Radius (Meters)</label>
                    <input 
                      type="number" 
                      value={newFence.radius_meters}
                      onChange={(e) => setNewFence({...newFence, radius_meters: Number(e.target.value)})}
                      className="w-full bg-dark-950 border border-dark-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div className="pt-2">
                    <button 
                      onClick={handleSaveNew}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-xl transition flex justify-center items-center gap-2"
                    >
                      <Save size={18} /> Save Zone
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* List of Existing Zones */}
            <div className="bg-dark-900 border border-dark-800 rounded-2xl p-6 h-[600px] overflow-y-auto">
              <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
                Active Zones ({geofences.length})
              </h2>
              
              <div className="space-y-4">
                {geofences.length === 0 && !loading && (
                  <p className="text-dark-500 text-center py-8">No geofences defined yet.</p>
                )}
                
                {geofences.map(geo => (
                  <div key={geo.id} className="bg-dark-950 border border-dark-800 rounded-xl p-4 transition hover:border-dark-700">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-medium text-lg">{geo.name}</h3>
                      <button 
                        onClick={() => handleDelete(geo.id)}
                        className="text-dark-500 hover:text-rose-500 transition p-1"
                        title="Delete Zone"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    <div className="text-sm text-dark-400 space-y-1">
                      <p>Radius: <span className="text-white">{geo.radius_meters}m</span></p>
                      <p>Lat: <span className="text-white">{geo.latitude.toFixed(4)}</span></p>
                      <p>Lng: <span className="text-white">{geo.longitude.toFixed(4)}</span></p>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${geo.is_active ? 'bg-emerald-500' : 'bg-dark-600'}`}></div>
                      <span className="text-xs text-dark-400">{geo.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
}
