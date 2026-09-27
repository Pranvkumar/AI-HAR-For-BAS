import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MissionOverview from '@/pages/MissionOverview';
import LiveMonitoring from '@/pages/LiveMonitoring';
import Experiments from '@/pages/Experiments';
import ExperimentDetails from '@/pages/ExperimentDetails';
import MicrogravityStatus from '@/pages/MicrogravityStatus';
import AlertsEvents from '@/pages/AlertsEvents';
import ActivityLogs from '@/pages/ActivityLogs';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MissionOverview />} />
        <Route path="/monitoring" element={<LiveMonitoring />} />
        <Route path="/experiments" element={<Experiments />} />
        <Route path="/experiments/:id" element={<ExperimentDetails />} />
        <Route path="/microgravity" element={<MicrogravityStatus />} />
        <Route path="/alerts" element={<AlertsEvents />} />
        <Route path="/logs" element={<ActivityLogs />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
