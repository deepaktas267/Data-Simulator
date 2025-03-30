import { useState } from 'react';
import SchemaEditor from './SchemaEditor';
import FormatSelector from './FormatSelector';
import DataPreview from './DataPreview';

const MainPanel = ({ activeTab, setGeneratedData, isGenerating, setIsGenerating, generatedData }) => {
  const [schema, setSchema] = useState({
    table_name: '',
    fields: [
      { name: ' ', type: 'select', mode: 'select', constraints: { pattern: '' } }
    ]
  });
  const [recordCount, setRecordCount] = useState(100);
  const [outputFormat, setOutputFormat] = useState('csv');
  const [showDataPreview, setShowDataPreview] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('http://localhost:8000/generate-data/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schema,
          record_count: recordCount,
          output_format: outputFormat
        })
      });
      const data = await response.json();
      setGeneratedData(data);
      setShowDataPreview(true);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateAsync = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('http://localhost:8000/generate-data-async/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schema,
          record_count: recordCount,
          output_format: outputFormat
        })
      });
      const data = await response.json();
      setTaskId(data.task_id);
      setTaskStatus({ status: 'PENDING' });
      // Start polling for task status
      pollTaskStatus(data.task_id);
    } catch (error) {
      console.error('Error:', error);
      setIsGenerating(false);
    }
  };

  const pollTaskStatus = async (taskId) => {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`http://localhost:8000/task-status/${taskId}`);
            const status = await response.json();
            setTaskStatus(status);
            
            if (status.status === 'SUCCESS' || status.status === 'FAILURE') {
                clearInterval(interval);
                setIsGenerating(false);
                if (status.status === 'SUCCESS') {
                    // The result now matches the sync endpoint response
                    setGeneratedData(status.result);
                    setShowDataPreview(true);
                }
            }
        } catch (error) {
            console.error('Error polling task status:', error);
            clearInterval(interval);
            setIsGenerating(false);
        }
    }, 1000);
};

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left Panel - Form */}
          <div className="lg:w-1/2">
            {activeTab === 'single-table' ? (
              <div className="space-y-6">
                <div className="bg-white rounded-lg shadow p-6">
                  <SchemaEditor schema={schema} setSchema={setSchema} />
                </div>
                
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">Generation Options</h3>
                    <div className="flex space-x-2">
                      <button
                        onClick={handleGenerate}
                        disabled={isGenerating}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md disabled:opacity-50"
                      >
                        {isGenerating ? 'Generating...' : 'Generate'}
                      </button>
                     
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Record Count</label>
                      <input
                        type="number"
                        value={recordCount}
                        onChange={(e) => setRecordCount(parseInt(e.target.value))}
                        min="1"
                        max="100000"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    
                    <FormatSelector outputFormat={outputFormat} setOutputFormat={setOutputFormat} />
                  </div>

                  {/* Task status display */}
                  {taskStatus && (
                    <div className="mt-4 p-3 rounded-md bg-gray-50 border border-gray-200">
                      <div className="flex justify-between items-center">
                        <span className="font-medium">Task Status:</span>
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          taskStatus.status === 'SUCCESS' ? 'bg-green-100 text-green-800' :
                          taskStatus.status === 'FAILURE' ? 'bg-red-100 text-red-800' :
                          taskStatus.status === 'PROGRESS' ? 'bg-blue-100 text-blue-800' :
                          'bg-yellow-100 text-yellow-800'
                        }`}>
                          {taskStatus.status}
                        </span>
                      </div>
                      {taskStatus.status === 'PROGRESS' && taskStatus.result && (
                        <div className="mt-2">
                          <div className="text-sm text-gray-600 mb-1">
                            Progress: {taskStatus.result.current} / {taskStatus.result.total}
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2.5">
                            <div 
                              className="bg-blue-600 h-2.5 rounded-full" 
                              style={{ width: `${(taskStatus.result.current / taskStatus.result.total) * 100}%` }}
                            ></div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow p-6">
                <div className="mb-6">
                  <h3 className="text-lg font-semibold mb-2">Relational Data Generator</h3>
                  <p className="text-gray-600">
                    This will generate a complete set of relational data including customers, products, orders, and order items.
                  </p>
                </div>
                
                <button
                  onClick={handleGenerateRelational}
                  disabled={isGenerating}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md disabled:opacity-50"
                >
                  {isGenerating ? 'Generating...' : 'Generate Relational Data'}
                </button>
              </div>
            )}
          </div>
          
          {/* Right Panel - Results */}
          <div className="lg:w-1/2">
            <div className="bg-white rounded-lg shadow p-6 h-full">
              {showDataPreview && generatedData ? (
                <DataPreview data={generatedData} />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">
                  <p>Generated data will appear here</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MainPanel;