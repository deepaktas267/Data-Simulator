import { useState } from 'react';
import Navbar from '../components/Navbar';
import MainPanel from '../components/MainPanel';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('single-table');
  const [generatedData, setGeneratedData] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white shadow-xl rounded-lg overflow-hidden">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-2xl font-bold text-gray-800">Welcome to Your Dashboard</h2>
            <p className="mt-1 text-gray-600">You're successfully authenticated</p>
          </div>
          
          <MainPanel 
            activeTab={activeTab} 
            setGeneratedData={setGeneratedData}
            isGenerating={isGenerating}
            setIsGenerating={setIsGenerating}
            generatedData={generatedData}
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;