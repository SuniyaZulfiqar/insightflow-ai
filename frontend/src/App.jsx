import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Database,
  Download,
  FileSpreadsheet,
  Lightbulb,
  ListChecks,
  LogOut,
  RefreshCw,
  Settings,
  Trash2,
  TrendingUp,
  Upload,
  Users,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const CHART_COLORS = [
  "#22d3ee",
  "#818cf8",
  "#2dd4bf",
  "#38bdf8",
  "#a78bfa",
  "#34d399",
  "#60a5fa",
  "#c084fc",
];

function capitalize(value) {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [datasets, setDatasets] = useState([]);
  const [dataset, setDataset] = useState(null);
  const [summary, setSummary] = useState(null);
  const [quality, setQuality] = useState(null);
  const [charts, setCharts] = useState([]);
  const [preview, setPreview] = useState(null);
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [dashboardReady, setDashboardReady] = useState(false);
  const [showCleaner, setShowCleaner] = useState(false);
  const [cleanMissing, setCleanMissing] = useState(true);
  const [cleanDuplicates, setCleanDuplicates] = useState(true);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleanPreview, setCleanPreview] = useState(null);
  const [cleanPreviewLoading, setCleanPreviewLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  const fileInputRef = useRef(null);
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));

  const headers = useMemo(
    () => ({
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    }),
    [token]
  );

  useEffect(() => {
    if (token) {
      loadDatasets();
      loadCurrentUser();
    } else {
      setLoading(false);
      setCurrentUser(null);
    }
  }, [token]);

  async function loadCurrentUser() {
    try {
      const data = await requestJson(`${API_URL}/users/me`, { headers });
      setCurrentUser(data);
    } catch (err) {
      console.error(err);
    }
  }

  function handleSessionExpired() {
    localStorage.removeItem("access_token");
    setToken(null);
    setDatasets([]);
    setDataset(null);
    setSummary(null);
    setQuality(null);
    setCharts([]);
    setPreview(null);
    setSelectedColumns([]);
    setDashboardReady(false);
    setCurrentUser(null);
    setError("Your session has expired. Please sign in again.");
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get("content-type") || "";
    let data = null;

    if (contentType.includes("application/json")) {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
    }

    if (response.status === 401) {
      handleSessionExpired();
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (!response.ok) {
      throw new Error(data?.detail || `Request failed (${response.status}).`);
    }

    return data;
  }

  async function previewCleaningChanges() {
    if (!dataset) return;

    try {
      setCleanPreviewLoading(true);
      setError("");
      const data = await requestJson(
        `${API_URL}/datasets/${dataset.id}/clean-preview`,
        {
          method: "POST",
          headers: {
            ...headers,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            fill_missing: cleanMissing,
            remove_duplicates: cleanDuplicates,
          }),
        }
      );
      setCleanPreview(data);
    } catch (err) {
      console.error(err);
      setCleanPreview(null);
      setError(err.message);
    } finally {
      setCleanPreviewLoading(false);
    }
  }

  useEffect(() => {
    if (!showCleaner || !dataset) return;
    previewCleaningChanges();
  }, [showCleaner, dataset?.id, cleanMissing, cleanDuplicates]);

  async function loadDatasets(preferredId = null) {
    try {
      setLoading(true);
      setError("");

      const data = await requestJson(`${API_URL}/datasets`, { headers });
      setDatasets(data);

      if (!data.length) {
        setDataset(null);
        setSummary(null);
        setQuality(null);
        setCharts([]);
        setPreview(null);
        setSelectedColumns([]);
        setDashboardReady(false);
        return;
      }

      const target =
        data.find((item) => item.id === Number(preferredId)) || data[0];

      await loadDataset(target, false);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDataset(selected, resetDashboard = true) {
    try {
      setPageLoading(true);
      setError("");
      setDataset(selected);

      const [analyticsData, qualityData] = await Promise.all([
        requestJson(`${API_URL}/datasets/${selected.id}/analytics`, {
          headers,
        }),
        requestJson(`${API_URL}/datasets/${selected.id}/quality`, {
          headers,
        }),
      ]);

      setSummary(analyticsData);
      setQuality(qualityData);

      if (resetDashboard) {
        setCharts([]);
        setDashboardReady(false);
        setSelectedColumns([]);
      }

      const previewData = await requestJson(
        `${API_URL}/datasets/${selected.id}/preview`,
        { headers }
      );
      setPreview(previewData);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  async function changeDataset(datasetId) {
    const selected = datasets.find((item) => item.id === Number(datasetId));
    if (!selected) return;
    await loadDataset(selected, true);
  }

  async function generateDashboard() {
    if (!dataset || !selectedColumns.length) {
      setError("Select at least one column before generating the dashboard.");
      return;
    }

    try {
      setPageLoading(true);
      setError("");
      const query = encodeURIComponent(selectedColumns.join(","));
      const data = await requestJson(
        `${API_URL}/datasets/${dataset.id}/charts?columns=${query}`,
        { headers }
      );

      setCharts(data.charts || []);
      setDashboardReady(true);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  function toggleColumn(columnName) {
    setSelectedColumns((current) => {
      if (current.includes(columnName)) {
        return current.filter((item) => item !== columnName);
      }

      if (current.length >= 6) {
        setError("You can select up to 6 columns for one dashboard.");
        return current;
      }

      return [...current, columnName];
    });
  }

  async function uploadDataset(event) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    const extension = file.name.toLowerCase().split(".").pop();
    if (!["csv", "xlsx", "xls"].includes(extension)) {
      setError("Unsupported file type. Please choose a CSV, XLSX, or XLS file.");
      return;
    }

    if (file.size === 0) {
      setError("The selected file is empty. Please choose a valid dataset.");
      return;
    }

    try {
      setUploading(true);
      setError("");
      setNotice("");

      const formData = new FormData();
      formData.append("file", file);

      const data = await requestJson(`${API_URL}/datasets/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        body: formData,
      });

      setNotice(`${data.name} was uploaded successfully.`);
      setActivePage("Dashboard");
      await loadDatasets(data.id);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  function openCleaningReview() {
    setError("");
    setCleanPreview(null);
    setShowCleaner(true);
  }

  async function applyCleaning() {
    if (!dataset || (!cleanMissing && !cleanDuplicates)) {
      setShowCleaner(false);
      return;
    }

    try {
      setCleaning(true);
      setError("");
      setNotice("");

      const result = await requestJson(
        `${API_URL}/datasets/${dataset.id}/clean`,
        {
          method: "POST",
          headers: {
            ...headers,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            fill_missing: cleanMissing,
            remove_duplicates: cleanDuplicates,
          }),
        }
      );

      setNotice(
        `Data cleaned: ${result.cleaned_missing_values} missing values filled and ${result.removed_duplicate_rows} duplicate rows removed.`
      );
      setShowCleaner(false);
      setCleanPreview(null);

      const currentSelectedColumns = [...selectedColumns];
      await loadDatasets(dataset.id);
      if (currentSelectedColumns.length) {
        const query = encodeURIComponent(currentSelectedColumns.join(","));
        const chartData = await requestJson(
          `${API_URL}/datasets/${dataset.id}/charts?columns=${query}`,
          { headers }
        );
        setCharts(chartData.charts || []);
        setDashboardReady(true);
      }
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setCleaning(false);
    }
  }

  async function refreshCurrentDataset() {
    if (!dataset) return;

    try {
      setPageLoading(true);
      setError("");

      const data = await requestJson(`${API_URL}/datasets`, { headers });
      setDatasets(data);

      const freshDataset = data.find((item) => item.id === dataset.id);
      if (!freshDataset) {
        setError("The selected dataset is no longer available.");
        return;
      }

      setDataset(freshDataset);

      const [analyticsData, qualityData, previewData] = await Promise.all([
        requestJson(`${API_URL}/datasets/${freshDataset.id}/analytics`, { headers }),
        requestJson(`${API_URL}/datasets/${freshDataset.id}/quality`, { headers }),
        requestJson(`${API_URL}/datasets/${freshDataset.id}/preview`, { headers }),
      ]);

      setSummary(analyticsData);
      setQuality(qualityData);
      setPreview(previewData);

      if (dashboardReady && selectedColumns.length) {
        const query = encodeURIComponent(selectedColumns.join(","));
        const chartData = await requestJson(
          `${API_URL}/datasets/${freshDataset.id}/charts?columns=${query}`,
          { headers }
        );
        setCharts(chartData.charts || []);
      }
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  async function deleteDataset(datasetId) {
    try {
      setPageLoading(true);
      setError("");

      await requestJson(`${API_URL}/datasets/${datasetId}`, {
        method: "DELETE",
        headers,
      });

      setNotice("Dataset deleted successfully.");

      const remaining = datasets.filter((item) => item.id !== datasetId);
      setDatasets(remaining);

      if (dataset?.id === datasetId) {
        if (remaining.length) {
          await loadDataset(remaining[0], true);
        } else {
          setDataset(null);
          setSummary(null);
          setQuality(null);
          setCharts([]);
          setPreview(null);
          setSelectedColumns([]);
          setDashboardReady(false);
        }
      }
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    setToken(null);
    setDatasets([]);
    setDataset(null);
    setSummary(null);
    setQuality(null);
    setCharts([]);
    setPreview(null);
    setSelectedColumns([]);
    setDashboardReady(false);
    setCurrentUser(null);
  }

  async function downloadFile(url, filename, expectedType = "application/pdf") {
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: expectedType,
      },
    });

    if (response.status === 401) {
      handleSessionExpired();
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (!response.ok) {
      let detail = "Could not download the requested file.";
      try {
        const data = await response.json();
        detail = data?.detail || detail;
      } catch {
        // The backend may return a non-JSON error body.
      }
      throw new Error(detail);
    }

    const contentType = response.headers.get("content-type") || "";
    if (expectedType && contentType.includes("application/json")) {
      let detail = "The server returned JSON instead of the requested file.";
      try {
        const data = await response.json();
        detail = data?.detail || detail;
      } catch {
        // Keep the safe fallback message.
      }
      throw new Error(detail);
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  async function downloadDatasetFile() {
    if (!dataset) {
      setError("Select a dataset before downloading the cleaned CSV.");
      return;
    }

    try {
      setPageLoading(true);
      setError("");

      await downloadFile(
        `${API_URL}/datasets/${dataset.id}/cleaned.csv`,
        "cleaned_data.csv",
        "text/csv"
      );
      setNotice("Cleaned CSV downloaded successfully.");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  async function downloadCleanedPdf() {
    if (!dataset) return;

    try {
      setPageLoading(true);
      setError("");
      await downloadFile(
        `${API_URL}/datasets/${dataset.id}/cleaned.pdf`,
        "cleaned_data.pdf"
      );
      setNotice("Cleaned PDF downloaded successfully.");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  async function downloadReport() {
    if (!dataset || !summary) return;

    try {
      setPageLoading(true);
      setError("");
      await downloadFile(
        `${API_URL}/datasets/${dataset.id}/report.pdf`,
        `${dataset.name}_InsightFlow_Report.pdf`
      );
      setNotice("PDF report downloaded successfully.");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  async function downloadDashboardPdf() {
    if (!dataset || !selectedColumns.length) {
      setError("Generate the dashboard first, then download its PDF.");
      return;
    }

    try {
      setPageLoading(true);
      setError("");
      const query = encodeURIComponent(selectedColumns.join(","));
      await downloadFile(
        `${API_URL}/datasets/${dataset.id}/dashboard.pdf?columns=${query}`,
        `${dataset.name}_InsightFlow_Dashboard.pdf`
      );
      setNotice("Dashboard PDF downloaded successfully.");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setPageLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loader" />
        <h2>Loading InsightFlow...</h2>
        <p>Preparing your analytics workspace.</p>
      </div>
    );
  }

  if (!token) {
    return <LoginPage />;
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <BarChart3 size={23} />
          </div>
          <div>
            <h2>InsightFlow</h2>
            <span>Business Intelligence</span>
          </div>
        </div>

        <nav className="navigation">
          {[
            ["Dashboard", <LayoutIcon />],
            ["Datasets", <Database size={19} />],
            ["Analytics", <TrendingUp size={19} />],
            ["AI Insights", <Lightbulb size={19} />],
            ["Reports", <BarChart3 size={19} />],
          ].map(([name, icon]) => (
            <button
              key={name}
              className={activePage === name ? "nav-item active" : "nav-item"}
              onClick={() => setActivePage(name)}
            >
              {icon}
              {name}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            className={activePage === "Settings" ? "nav-item active" : "nav-item"}
            onClick={() => setActivePage("Settings")}
          >
            <Settings size={19} />
            Settings
          </button>
          <button className="nav-item logout" onClick={logout}>
            <LogOut size={19} />
            Logout
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">WORKSPACE</p>
            <h1>{activePage}</h1>
          </div>
          <div className="user-area">
            <div className="avatar">
              {currentUser?.name ? currentUser.name.trim().charAt(0).toUpperCase() : "U"}
            </div>
            <div className="user-details">
              <strong>{currentUser?.name || "Loading..."}</strong>
              <span>{currentUser?.role ? capitalize(currentUser.role) : ""}</span>
            </div>
          </div>
        </header>

        {error && (
          <div className="error-box">
            <AlertTriangle size={19} />
            <span>{error}</span>
            <button onClick={() => setError("")}>
              <X size={17} />
            </button>
          </div>
        )}

        {notice && (
          <div className="notice-box">
            <CheckCircle2 size={19} />
            <span>{notice}</span>
            <button onClick={() => setNotice("")}>
              <X size={17} />
            </button>
          </div>
        )}

        {activePage === "Dashboard" && (
          <Dashboard
            dataset={dataset}
            datasets={datasets}
            summary={summary}
            quality={quality}
            preview={preview}
            charts={charts}
            selectedColumns={selectedColumns}
            dashboardReady={dashboardReady}
            pageLoading={pageLoading}
            onDatasetChange={changeDataset}
            onUpload={() => fileInputRef.current?.click()}
            onToggleColumn={toggleColumn}
            onGenerate={generateDashboard}
            onClean={openCleaningReview}
            onRefresh={refreshCurrentDataset}
            onDownloadPdf={downloadDashboardPdf}
            onDownloadDataset={downloadDatasetFile}
          />
        )}

        {activePage === "Datasets" && (
          <DatasetsPage
            datasets={datasets}
            dataset={dataset}
            preview={preview}
            quality={quality}
            uploading={uploading}
            onUpload={() => fileInputRef.current?.click()}
            onSelect={changeDataset}
            onClean={openCleaningReview}
            onRefresh={refreshCurrentDataset}
            onDownloadDataset={downloadDatasetFile}
            onDownloadCleanedPdf={downloadCleanedPdf}
            onDelete={deleteDataset}
          />
        )}

        {activePage === "Analytics" && (
          <AnalyticsPage
            summary={summary}
            charts={charts}
            selectedColumns={selectedColumns}
            onToggleColumn={toggleColumn}
            onGenerate={generateDashboard}
            dataset={dataset}
          />
        )}

        {activePage === "AI Insights" && (
          <InsightsPage summary={summary} quality={quality} dataset={dataset} />
        )}

        {activePage === "Reports" && (
          <ReportsPage
            dataset={dataset}
            summary={summary}
            quality={quality}
            onDownload={downloadReport}
          />
        )}

        {activePage === "Settings" && <SettingsPage />}
      </main>

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden-file-input"
        onChange={uploadDataset}
      />

      {showCleaner && (
        <CleaningModal
          quality={quality}
          fillMissing={cleanMissing}
          removeDuplicates={cleanDuplicates}
          setFillMissing={setCleanMissing}
          setRemoveDuplicates={setCleanDuplicates}
          cleaning={cleaning}
          cleanPreview={cleanPreview}
          cleanPreviewLoading={cleanPreviewLoading}
          onClose={() => { setShowCleaner(false); setCleanPreview(null); }}
          onApply={applyCleaning}
          onPreview={previewCleaningChanges}
          onDownloadCleanedPdf={downloadCleanedPdf}
        />
      )}
    </div>
  );
}

function LayoutIcon() {
  return <span className="layout-icon"><BarChart3 size={19} /></span>;
}

function Dashboard({
  dataset,
  datasets,
  summary,
  quality,
  preview,
  charts,
  selectedColumns,
  dashboardReady,
  pageLoading,
  onDatasetChange,
  onUpload,
  onToggleColumn,
  onGenerate,
  onClean,
  onRefresh,
  onDownloadPdf,
  onDownloadDataset,
}) {
  const [previewOpen, setPreviewOpen] = useState(true);
  const [builderOpen, setBuilderOpen] = useState(true);

  if (!dataset) {
    return (
      <div className="empty-page">
        <div className="empty-icon"><Database size={34} /></div>
        <h2>No dataset yet</h2>
        <p>Upload a CSV, XLSX, or XLS file to start building your dashboard.</p>
        <button className="primary-button" onClick={onUpload}>
          <Upload size={18} /> Upload Dataset
        </button>
      </div>
    );
  }

  const availableColumns = summary?.columns || [];

  return (
    <section className="dashboard">
      <div className="dashboard-header">
        <div>
          <p className="eyebrow">BUSINESS INTELLIGENCE</p>
          <h2>Build Your Dashboard</h2>
          <p>
            Choose the columns you want to analyze. InsightFlow automatically applies the right aggregation and visualization to each field.
          </p>
        </div>

        <div className="dashboard-controls">
          <div className="dashboard-select-row">
            <select
              value={dataset.id}
              onChange={(event) => onDatasetChange(event.target.value)}
              className="dataset-select"
              aria-label="Select dataset"
            >
              {datasets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <button className="secondary-button" onClick={onRefresh} disabled={pageLoading}>
              <RefreshCw size={17} className={pageLoading ? "spin" : ""} />
              {pageLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
          <div className="dashboard-action-row">
            <button className="secondary-button" onClick={onDownloadPdf} disabled={!dashboardReady || pageLoading}>
              <Download size={17} /> Dashboard PDF
            </button>
            <button className="secondary-button" onClick={onDownloadDataset} disabled={!dataset || pageLoading}>
              <FileSpreadsheet size={17} /> Download Cleaned CSV
            </button>
            <button className="primary-button dashboard-upload-button" onClick={onUpload}>
              <Upload size={17} /> Upload Dataset
            </button>
          </div>
        </div>
      </div>

      <div className="dataset-info">
        <Database size={20} />
        <div className="dataset-info-main">
          <strong>{dataset.filename}</strong>
          <span>
            {dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns ·{" "}
            {dataset.file_type.toUpperCase()}
          </span>
        </div>
        <span className="dataset-pill">{summary?.measure_columns || 0} measures</span>
        <span className="dataset-pill">{summary?.numeric_dimension_columns || 0} numeric dimensions</span>
        <span className="dataset-pill">{summary?.categorical_columns || 0} categorical</span>
        <span className="dataset-pill">{summary?.identifier_columns || 0} identifiers</span>
        <span className="dataset-pill">{summary?.date_columns || 0} date</span>
      </div>

      {preview && (
        <section className={`dashboard-preview-card collapsible-card ${previewOpen ? "is-open" : "is-collapsed"}`}>
          <button
            type="button"
            className="collapsible-header"
            onClick={() => setPreviewOpen((value) => !value)}
            aria-expanded={previewOpen}
          >
            <div className="collapsible-heading">
              <div className="section-icon preview-icon"><Database size={18} /></div>
              <div>
                <p className="eyebrow">DATA PREVIEW</p>
                <h3>Current dataset</h3>
                <p>Review the actual values before building your dashboard or cleaning the data.</p>
              </div>
            </div>
            <div className="collapsible-header-meta">
              <span className="selection-count">{preview.row_count.toLocaleString()} total rows</span>
              <span className="collapse-button" aria-hidden="true">
                {previewOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </span>
            </div>
          </button>
          {previewOpen && (
            <div className="collapsible-content">
              <div className="preview-meta-row">
                <span>Showing the first {preview.preview?.length || 0} rows</span>
                <span>{preview.columns.length} columns</span>
              </div>
              <div className="table-wrap preview-table-wrap">
                <table>
                  <thead>
                    <tr>
                      {preview.columns.map((column) => <th key={column}>{column}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row, index) => (
                      <tr key={index}>
                        {preview.columns.map((column) => (
                          <td key={column}>{row[column] === null || row[column] === "" ? <span className="null-value">NULL</span> : String(row[column])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      <QualitySummary quality={quality} onClean={onClean} />

      <section className={`selector-card collapsible-card ${builderOpen ? "is-open" : "is-collapsed"}`}>
        <button
          type="button"
          className="collapsible-header"
          onClick={() => setBuilderOpen((value) => !value)}
          aria-expanded={builderOpen}
        >
          <div className="collapsible-heading">
            <div className="section-icon builder-icon"><BarChart3 size={18} /></div>
            <div>
              <p className="eyebrow">DASHBOARD BUILDER</p>
              <h3>Which columns do you want to see?</h3>
              <p>Select up to 6 columns. Each field is analyzed according to its business meaning.</p>
            </div>
          </div>
          <div className="collapsible-header-meta">
            <span className="selection-count">{selectedColumns.length}/6 selected</span>
            <span className="collapse-button" aria-hidden="true">
              {builderOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </span>
          </div>
        </button>

        {builderOpen && <div className="collapsible-content">
        <div className="column-selector">
          {availableColumns.map((column) => (
            <button
              key={column.name}
              className={
                selectedColumns.includes(column.name)
                  ? "column-option selected"
                  : "column-option"
              }
              onClick={() => onToggleColumn(column.name)}
            >
              <span className="column-type">
                {String(column.role || column.type).replace("_", " ")}
              </span>
              <strong>{column.name}</strong>
              <span>
                {column.unique.toLocaleString()} unique · {column.missing.toLocaleString()} missing
              </span>
            </button>
          ))}
        </div>

        <div className="builder-footer">
          <span>
            {pageLoading ? "Preparing analytics..." : selectedColumns.length ? `${selectedColumns.length} column${selectedColumns.length === 1 ? "" : "s"} ready to visualize.` : "Select at least one column to begin."}
          </span>
          <button
            className="primary-button"
            disabled={!selectedColumns.length || pageLoading}
            onClick={onGenerate}
          >
            <BarChart3 size={18} />
            Generate Dashboard
          </button>
        </div>
        </div>}
      </section>

      {dashboardReady ? (
        <section className="charts-grid generated-charts">
          {charts.map((chart) => (
            <DynamicChart key={chart.name} chart={chart} />
          ))}
        </section>
      ) : (
        <div className="empty-chart-state">
          <BarChart3 size={30} />
          <h3>Select columns to create your dashboard</h3>
          <p>Your selected visualizations will appear here.</p>
        </div>
      )}
    </section>
  );
}

function ChartTooltip({ active, payload, chart }) {
  if (!active || !payload?.length) return null;

  const point = payload[0]?.payload || {};
  const label = point.label ?? payload[0]?.name ?? "Unknown";
  const value = payload[0]?.value ?? 0;

  return (
    <div
      style={{
        background: "#171d28",
        border: "1px solid #303644",
        borderRadius: 8,
        color: "#fff",
        padding: "8px 10px",
      }}
    >
      <div style={{ marginBottom: 4 }}>{chart.name}: {String(label)}</div>
      <div>{chart.metric_label || "Records"}: {String(value)}</div>
    </div>
  );
}

function DynamicChart({ chart }) {
  const role = chart.role || chart.type;
  const isPie = chart.chart === "pie";
  const isSummary = chart.chart === "summary";
  const rawData = Array.isArray(chart.data) ? chart.data : [];
  const categoryCount = rawData.length;

  const displayData = rawData
    .slice(0, isPie ? 8 : 10)
    .map((item) => ({
      ...item,
      label: String(item.label ?? "Unknown"),
      value: Number(item.value ?? 0),
    }));

  const visibleCount = displayData.length;
  const labelLength = Math.max(
    12,
    ...displayData.map((item) => item.label.length)
  );

  const chartHeight = isPie
    ? Math.max(390, 350 + Math.ceil(visibleCount / 4) * 30)
    : Math.max(380, 230 + visibleCount * 30);

  const shortenLabel = (value) =>
    value.length > 26 ? `${value.slice(0, 23)}...` : value;

  const semanticColors = {
    high: "#ef4444",
    medium: "#f59e0b",
    low: "#10b981",
    positive: "#10b981",
    neutral: "#64748b",
    negative: "#ef4444",
    resolved: "#10b981",
    closed: "#10b981",
    pending: "#f59e0b",
    open: "#3b82f6",
    escalated: "#ef4444",
  };

  const getPieColor = (label, index) =>
    semanticColors[String(label).toLowerCase()] ||
    CHART_COLORS[index % CHART_COLORS.length];

  const roleLabel = {
    measure: "MEASURE",
    numeric_dimension: "NUMERIC DISTRIBUTION",
    identifier: "IDENTIFIER",
    categorical: "CATEGORY",
    date: "TIME SERIES",
    text: "TEXT SUMMARY",
  }[role] || String(chart.type || "DATA").toUpperCase();

  return (
    <article
      className={`chart-card dynamic-chart ${isPie ? "pie-chart-card" : ""} role-${role}`}
    >
      <div className="chart-header">
        <div className="chart-title-block">
          <p className="chart-type">{roleLabel}</p>
          <h3 title={String(chart.name)}>{chart.name}</h3>
          <p>{chart.description}</p>
        </div>
        <span className="chart-total">
          {chart.unique_count?.toLocaleString?.() ?? chart.unique_count ?? 0} unique
        </span>
      </div>

      {displayData.length === 0 ? (
        <div className="chart-empty-data">
          <BarChart3 size={28} />
          <strong>No data available</strong>
          <span>This field does not contain usable values for analysis.</span>
        </div>
      ) : isSummary ? (
        <div className="metric-grid">
          {displayData.map((item) => (
            <div className="metric-tile" key={`${chart.name}-${item.label}`}>
              <span>{item.label}</span>
              <strong>{Number.isFinite(item.value) ? item.value.toLocaleString() : item.value}</strong>
            </div>
          ))}
        </div>
      ) : (
        <div className="chart-body">
          {isPie ? (
            <>
              <ResponsiveContainer width="100%" height={chartHeight - 112}>
                <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                <Pie
                  data={displayData}
                  dataKey="value"
                  nameKey="label"
                  cx="50%"
                  cy="42%"
                  outerRadius={92}
                  innerRadius={52}
                  paddingAngle={2}
                  stroke="#121620"
                  strokeWidth={2}
                >
                  {displayData.map((item, index) => (
                    <Cell
                      key={`${chart.name}-${index}`}
                      fill={getPieColor(item.label, index)}
                    />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip chart={chart} />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pie-legend" aria-label={`${chart.name} legend`}>
              {displayData.map((item, index) => (
                <span className="pie-legend-item" key={`${chart.name}-legend-${index}`}>
                  <i style={{ background: getPieColor(item.label, index) }} />
                  <span title={item.label}>{shortenLabel(item.label)}</span>
                </span>
                ))}
              </div>
            </>
          ) : (
            <ResponsiveContainer width="100%" height={chartHeight - 112}>
              <BarChart
                data={displayData}
                layout="vertical"
                margin={{
                  top: 10,
                  right: 24,
                  left: Math.min(170, Math.max(82, labelLength * 5.5)),
                  bottom: 12,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#292e39"
                  horizontal={false}
                />
                <XAxis
                  type="number"
                  allowDecimals={role === "numeric_dimension" ? false : true}
                  tick={{ fill: "#9ca5b7", fontSize: 11 }}
                  axisLine={{ stroke: "#303541" }}
                  tickLine={{ stroke: "#303541" }}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={Math.min(170, Math.max(82, labelLength * 5.5))}
                  tick={{ fill: "#c0c7d4", fontSize: 11 }}
                  tickFormatter={shortenLabel}
                  interval={0}
                  axisLine={{ stroke: "#303541" }}
                  tickLine={{ stroke: "#303541" }}
                />
                <Tooltip content={<ChartTooltip chart={chart} />} />
                <Bar
                  dataKey="value"
                  fill={
                    role === "date"
                      ? "#22d3ee"
                      : role === "numeric_dimension"
                        ? "#818cf8"
                        : "#2dd4bf"
                  }
                  radius={[0, 6, 6, 0]}
                  barSize={Math.max(
                    12,
                    Math.min(26, 180 / Math.max(1, visibleCount))
                  )}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {categoryCount > displayData.length && (
        <div className="chart-footnote">
          Showing the top {displayData.length} of {categoryCount} values.
        </div>
      )}

      {chart.aggregation && (
        <div className="chart-method">
          Analysis: <strong>{chart.aggregation}</strong>
        </div>
      )}
    </article>
  );
}

function QualitySummary({ quality, onClean }) {
  if (!quality) return null;

  const missing = quality.missing_values?.count || 0;
  const duplicates = quality.duplicate_rows || 0;

  return (
    <section className="quality-card">
      <div className="quality-icon"><ListChecks size={22} /></div>
      <div className="quality-content">
        <div className="quality-title-row">
          <div>
            <p className="eyebrow">DATA QUALITY</p>
            <h3>Review before changing your data</h3>
          </div>
          <span className={missing || duplicates ? "quality-badge warning" : "quality-badge success"}>
            {missing || duplicates ? "Needs review" : "Clean"}
          </span>
        </div>
        <div className="quality-metrics">
          <span><strong>{missing}</strong> missing cells</span>
          <span><strong>{duplicates}</strong> duplicate rows</span>
          <span><strong>{quality.cleanable_missing_values || 0}</strong> fillable cells</span>
        </div>
      </div>
      <button className="secondary-button" onClick={onClean}>
        <ListChecks size={17} />
        Review & Clean
      </button>
    </section>
  );
}

function DatasetsPage({
  datasets,
  dataset,
  preview,
  quality,
  uploading,
  onUpload,
  onSelect,
  onClean,
  onRefresh,
  onDownloadDataset,
  onDownloadCleanedPdf,
  onDelete,
}) {
  const [previewOpen, setPreviewOpen] = useState(true);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);

  function handleDeleteClick(event, datasetId) {
    event.stopPropagation();
    setPendingDeleteId(datasetId);
  }

  function confirmDelete(event, datasetId) {
    event.stopPropagation();
    setPendingDeleteId(null);
    onDelete?.(datasetId);
  }

  function cancelDelete(event) {
    event.stopPropagation();
    setPendingDeleteId(null);
  }

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">DATA MANAGEMENT</p>
          <h2>Datasets</h2>
          <p>Upload, inspect, clean and prepare any CSV or Excel dataset.</p>
        </div>
        <button className="primary-button" onClick={onUpload} disabled={uploading}>
          <Upload size={18} />
          {uploading ? "Uploading..." : "Upload Dataset"}
        </button>
      </div>

      <div className="dataset-list">
        {datasets.map((item) => (
          <div
            key={item.id}
            className={dataset?.id === item.id ? "dataset-list-item selected" : "dataset-list-item"}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(item.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") onSelect(item.id);
            }}
          >
            <FileSpreadsheet size={22} />
            <div>
              <strong>{item.name}</strong>
              <span>{item.row_count.toLocaleString()} rows · {item.column_count} columns</span>
            </div>

            {pendingDeleteId === item.id ? (
              <div className="dataset-delete-confirm" onClick={(event) => event.stopPropagation()}>
                <span>Delete?</span>
                <button
                  type="button"
                  className="dataset-delete-confirm-yes"
                  onClick={(event) => confirmDelete(event, item.id)}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className="dataset-delete-confirm-no"
                  onClick={cancelDelete}
                >
                  No
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="dataset-delete-button"
                onClick={(event) => handleDeleteClick(event, item.id)}
                aria-label={`Delete ${item.name}`}
                title="Delete dataset"
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        ))}
      </div>

      {dataset && preview && (
        <>
          <div className={`page-card collapsible-card ${previewOpen ? "is-open" : "is-collapsed"}`}>
            <div className="collapsible-header dataset-preview-header">
              <div className="collapsible-heading">
                <div className="section-icon preview-icon"><FileSpreadsheet size={18} /></div>
                <div>
                  <p className="eyebrow">DATA PREVIEW</p>
                  <h3>{dataset.filename}</h3>
                  <p>Inspect the current dataset without taking over the page.</p>
                </div>
              </div>
              <div className="collapsible-header-meta">
                <div className="header-actions compact-actions">
                  <button className="secondary-button" type="button" onClick={onRefresh} disabled={uploading}>
                    <RefreshCw size={16} /> Refresh
                  </button>
                  <button className="secondary-button" type="button" onClick={onClean}>
                    <ListChecks size={16} /> Review & Clean
                  </button>
                  <button className="secondary-button" type="button" onClick={onDownloadDataset}>
                    <FileSpreadsheet size={16} /> Download {dataset.file_type.toUpperCase()}
                  </button>
                  <button className="secondary-button" type="button" onClick={onDownloadCleanedPdf}>
                    <Download size={16} /> Download PDF
                  </button>
                </div>
                <button
                  type="button"
                  className="collapse-button"
                  onClick={() => setPreviewOpen((value) => !value)}
                  aria-expanded={previewOpen}
                  aria-label={previewOpen ? "Collapse data preview" : "Expand data preview"}
                >
                  {previewOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </button>
              </div>
            </div>

            {previewOpen && (
              <div className="collapsible-content">
                <div className="preview-meta-row">
                  <span>Showing the first {preview.preview?.length || 0} rows</span>
                  <span>{preview.row_count.toLocaleString()} total rows · {preview.columns.length} columns</span>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {preview.columns.map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.preview.map((row, index) => (
                        <tr key={index}>
                          {preview.columns.map((column) => (
                            <td key={column}>{row[column] === null || row[column] === "" ? <span className="null-value">NULL</span> : String(row[column])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          <QualitySummary quality={quality} onClean={onClean} />
        </>
      )}
    </section>
  );
}

function AnalyticsPage({
  summary,
  charts,
  selectedColumns,
  onToggleColumn,
  onGenerate,
  dataset,
}) {
  if (!dataset || !summary) {
    return (
      <div className="empty-page">
        <TrendingUp size={40} />
        <h2>No analytics available</h2>
        <p>Upload a dataset first.</p>
      </div>
    );
  }

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">DATA ANALYTICS</p>
          <h2>Explore {dataset.name}</h2>
          <p>Profile every column and choose exactly what you want to visualize.</p>
        </div>
      </div>

      <div className="analytics-kpis">
        <MiniMetric title="Rows" value={summary.total_rows.toLocaleString()} />
        <MiniMetric title="Columns" value={summary.total_columns} />
        <MiniMetric title="Missing Cells" value={summary.missing_values.count} />
        <MiniMetric title="Duplicate Rows" value={summary.duplicate_rows} />
        <MiniMetric title="Measures" value={summary.measure_columns ?? summary.numeric_columns} />
        <MiniMetric title="Numeric Dimensions" value={summary.numeric_dimension_columns || 0} />
      </div>

      <div className="profile-table-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">COLUMN PROFILING</p>
            <h3>Select columns for visualization</h3>
          </div>
          <button className="primary-button" onClick={onGenerate} disabled={!selectedColumns.length}>
            <BarChart3 size={17} /> Generate
          </button>
        </div>

        <div className="profile-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Select</th>
                <th>Column</th>
                <th>Type</th>
                <th>Role</th>
                <th>Unique</th>
                <th>Missing</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {summary.columns.map((column) => (
                <tr key={column.name}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedColumns.includes(column.name)}
                      onChange={() => onToggleColumn(column.name)}
                    />
                  </td>
                  <td><strong>{column.name}</strong></td>
                  <td><span className="type-badge">{column.type}</span></td>
                  <td><span className="role-badge">{String(column.role || "data").replace("_", " ")}</span></td>
                  <td>{column.unique.toLocaleString()}</td>
                  <td>{column.missing.toLocaleString()}</td>
                  <td>
                    {column.role === "measure" && column.statistics
                      ? `Total ${column.statistics.sum ?? "—"} · Avg ${column.statistics.mean ?? "—"} · Median ${column.statistics.median ?? "—"}`
                      : column.role === "numeric_dimension" && column.statistics
                        ? `Avg ${column.statistics.mean ?? "—"} · Min ${column.statistics.min ?? "—"} · Max ${column.statistics.max ?? "—"}`
                        : column.role === "identifier"
                          ? "Use count / unique count; do not sum IDs"
                          : column.top_values
                            ? column.top_values.slice(0, 3).map((item) => `${item.label}: ${item.value}`).join(" · ")
                            : column.text_statistics
                              ? `Avg ${column.text_statistics.average_length} chars`
                              : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {charts.length > 0 && (
        <div className="charts-grid generated-charts analytics-results">
          {charts.map((chart) => <DynamicChart key={chart.name} chart={chart} />)}
        </div>
      )}
    </section>
  );
}

function MiniMetric({ title, value }) {
  return (
    <div className="mini-metric">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InsightsPage({ summary, quality, dataset }) {
  if (!dataset || !summary) {
    return (
      <div className="empty-page">
        <Lightbulb size={40} />
        <h2>No insights yet</h2>
        <p>Upload a dataset to generate automated insights.</p>
      </div>
    );
  }

  const insights = buildInsights(summary, quality);

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">INSIGHTFLOW AI</p>
          <h2>Automated Data Insights</h2>
          <p>Generic insights generated from the structure and quality of your dataset.</p>
        </div>
      </div>

      <div className="insight-grid">
        {insights.map((item) => (
          <div className="insight-card" key={item.title}>
            <div className="insight-icon">{item.icon}</div>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function buildInsights(summary, quality) {
  const insights = [];

  const topNumeric = summary.top_numeric;
  const topCategorical = summary.top_categorical;

  if (topCategorical) {
    insights.push({
      title: "Largest Category",
      icon: <TrendingUp size={21} />,
      text: `${topCategorical.name} has ${topCategorical.unique} unique categories. The most common value is "${topCategorical.top_values?.[0]?.label}" with ${topCategorical.top_values?.[0]?.value} records.`,
    });
  }

  if (topNumeric) {
    insights.push({
      title: "Numeric Signal",
      icon: <BarChart3 size={21} />,
      text: `${topNumeric.name} ranges from ${topNumeric.statistics.min} to ${topNumeric.statistics.max}, with an average of ${topNumeric.statistics.mean}.`,
    });
  }

  insights.push({
    title: "Data Completeness",
    icon: <CheckCircle2 size={21} />,
    text:
      quality?.missing_values?.count > 0
        ? `${quality.missing_values.count} cells are missing. ${quality.cleanable_missing_values || 0} can be automatically filled using the available data patterns.`
        : "No missing cells were detected in the current dataset.",
  });

  insights.push({
    title: "Duplicate Risk",
    icon: <Trash2 size={21} />,
    text:
      quality?.duplicate_rows > 0
        ? `${quality.duplicate_rows} exact duplicate rows were detected. Review them before applying the cleanup.`
        : "No exact duplicate rows were detected.",
  });

  return insights;
}

function ReportsPage({ dataset, summary, quality, onDownload, downloading }) {
  if (!dataset || !summary) {
    return (
      <div className="empty-page">
        <Download size={40} />
        <h2>No report available</h2>
        <p>Upload and analyze a dataset first.</p>
      </div>
    );
  }

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">REPORTING</p>
          <h2>Reports</h2>
          <p>Export the current dataset profile, quality findings and dashboard selection.</p>
        </div>
        <button type="button" className="primary-button" onClick={onDownload} disabled={downloading}>
          <Download size={18} /> {downloading ? "Generating PDF..." : "Download PDF Report"}
        </button>
      </div>

      <div className="report-grid">
        <MiniMetric title="Dataset" value={dataset.name} />
        <MiniMetric title="Rows" value={summary.total_rows.toLocaleString()} />
        <MiniMetric title="Columns" value={summary.total_columns} />
        <MiniMetric title="Missing Cells" value={quality?.missing_values?.count || 0} />
        <MiniMetric title="Duplicates" value={quality?.duplicate_rows || 0} />
      </div>

      <div className="page-card">
        <p className="eyebrow">REPORT CONTENT</p>
        <h3>What is included?</h3>
        <ul className="report-list">
          <li>Dataset metadata and row/column counts</li>
          <li>Column types and statistical profiling</li>
          <li>Missing-value and duplicate-row analysis</li>
          <li>Selected dashboard columns</li>
          <li>Data-quality recommendations</li>
        </ul>
      </div>
    </section>
  );
}

function SettingsPage() {
  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE</p>
          <h2>Settings</h2>
          <p>Current InsightFlow analysis settings.</p>
        </div>
      </div>

      <div className="page-card settings-card">
        <div className="settings-row">
          <span>API URL</span>
          <strong>{API_URL}</strong>
        </div>
        <div className="settings-row">
          <span>Supported files</span>
          <strong>CSV, XLSX, XLS</strong>
        </div>
        <div className="settings-row">
          <span>Dashboard columns</span>
          <strong>Up to 6 per dashboard</strong>
        </div>
        <div className="settings-row">
          <span>Cleaning mode</span>
          <strong>User-confirmed</strong>
        </div>
      </div>
    </section>
  );
}

function CleaningModal({
  quality,
  fillMissing,
  removeDuplicates,
  setFillMissing,
  setRemoveDuplicates,
  cleaning,
  cleanPreview,
  cleanPreviewLoading,
  onClose,
  onApply,
  onPreview,
  onDownloadCleanedPdf,
}) {
  const missing = quality?.missing_values?.count || 0;
  const duplicates = quality?.duplicate_rows || 0;
  const before = cleanPreview?.before || {
    rows: cleanPreview?.original_rows ?? quality?.total_rows ?? 0,
    missing_values: cleanPreview?.original_missing_values ?? missing,
    duplicate_rows: cleanPreview?.original_duplicate_rows ?? duplicates,
    preview: cleanPreview?.original_preview || [],
  };
  const after = cleanPreview?.after || {
    rows: cleanPreview?.preview_rows ?? cleanPreview?.final_rows ?? before.rows,
    missing_values: cleanPreview?.preview_missing_values ?? cleanPreview?.remaining_missing_values ?? before.missing_values,
    duplicate_rows: cleanPreview?.preview_duplicate_rows ?? cleanPreview?.remaining_duplicate_rows ?? before.duplicate_rows,
    preview: cleanPreview?.cleaned_preview || [],
  };
  const previewColumns = cleanPreview?.columns || Object.keys(before.preview?.[0] || after.preview?.[0] || {});

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-header">
          <div>
            <p className="eyebrow">DATA CLEANING</p>
            <h2>Review proposed amendments</h2>
          </div>
          <button className="icon-button" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <p className="modal-description">
          InsightFlow first prepares a proposed version of the data. Nothing is written to the dataset until you approve the amendments below.
        </p>

        <div className="clean-summary-grid">
          <div className="clean-summary-tile">
            <span>Missing values</span>
            <strong>{before.missing_values}</strong>
            <small>→ {after.missing_values} after</small>
          </div>
          <div className="clean-summary-tile">
            <span>Duplicate rows</span>
            <strong>{before.duplicate_rows}</strong>
            <small>→ {after.duplicate_rows} after</small>
          </div>
          <div className="clean-summary-tile">
            <span>Rows</span>
            <strong>{before.rows}</strong>
            <small>→ {after.rows} after</small>
          </div>
        </div>

        <label className="clean-option">
          <input
            type="checkbox"
            checked={fillMissing}
            onChange={(event) => setFillMissing(event.target.checked)}
            disabled={!missing}
          />
          <div>
            <strong>Fill replaceable missing values</strong>
            <span>
              {quality?.cleanable_missing_values || 0} cells are eligible. InsightFlow uses the detected data type and available group patterns instead of applying one rule to every column.
            </span>
          </div>
        </label>

        <label className="clean-option">
          <input
            type="checkbox"
            checked={removeDuplicates}
            onChange={(event) => setRemoveDuplicates(event.target.checked)}
            disabled={!duplicates}
          />
          <div>
            <strong>Remove exact duplicate rows</strong>
            <span>{duplicates} duplicate rows were detected and will only be removed after approval.</span>
          </div>
        </label>

        <div className="clean-preview-section">
          <div className="clean-preview-heading">
            <div>
              <p className="eyebrow">PROPOSED CHANGE</p>
              <h3>Preview before applying</h3>
            </div>
            <div className="preview-actions">
              {cleanPreviewLoading && <span className="preview-loading"><RefreshCw size={14} className="spin" /> Updating...</span>}
              <button type="button" className="secondary-button compact-preview-button" onClick={onPreview} disabled={cleanPreviewLoading}>
                <RefreshCw size={15} className={cleanPreviewLoading ? "spin" : ""} /> Preview Changes
              </button>
            </div>
          </div>

          {cleanPreview ? (
            <div className="clean-preview-grid">
              <div className="clean-preview-pane">
                <div className="clean-preview-pane-title">Current data</div>
                <div className="clean-preview-table-wrap">
                  {before.preview?.length ? (
                    <table>
                      <thead><tr>{previewColumns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                      <tbody>
                        {before.preview.map((row, index) => (
                          <tr key={index}>{previewColumns.map((column) => <td key={column}>{row[column] === null || row[column] === "" ? <span className="null-value">NULL</span> : String(row[column])}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <div className="clean-preview-empty">No preview rows available.</div>}
                </div>
              </div>
              <div className="clean-preview-pane proposed">
                <div className="clean-preview-pane-title">Proposed data</div>
                <div className="clean-preview-table-wrap">
                  {after.preview?.length ? (
                    <table>
                      <thead><tr>{previewColumns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                      <tbody>
                        {after.preview.map((row, index) => (
                          <tr key={index}>{previewColumns.map((column) => <td key={column}>{row[column] === null || row[column] === "" ? <span className="null-value">NULL</span> : String(row[column])}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <div className="clean-preview-empty">No proposed rows available.</div>}
                </div>
              </div>
            </div>
          ) : (
            <div className="clean-preview-empty">
              <ListChecks size={24} />
              <span>{cleanPreviewLoading ? "Preparing a safe before/after preview..." : "No changes are selected."}</span>
            </div>
          )}

          {cleanPreview?.cleaning_actions?.length > 0 && (
            <div className="cleaning-actions-list">
              <strong>Proposed amendments</strong>
              {cleanPreview.cleaning_actions.map((action, index) => (
                <div key={index} className="cleaning-action-row">
                  <span>{action.column || "Duplicate rows"}</span>
                  <span>{action.filled ? `${action.filled} values` : `${action.removed || 0} rows`}</span>
                  <small>{action.method}</small>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose} disabled={cleaning}>
            Cancel
          </button>
          <button className="primary-button" onClick={onApply} disabled={cleaning || !cleanPreview?.has_changes}>
            {cleaning ? "Applying..." : cleanPreview?.has_changes ? "Apply Amendments" : "No Changes to Apply"}
          </button>
        </div>
      </div>
    </div>
  );
}

function LoginPage() {
  const [view, setView] = useState("login"); // "login" | "signup" | "verify"

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  const [signupError, setSignupError] = useState("");
  const [signingUp, setSigningUp] = useState(false);

  const [verifyError, setVerifyError] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [infoMessage, setInfoMessage] = useState("");

  async function handleLogin(event) {
    event.preventDefault();

    try {
      setLoggingIn(true);
      setLoginError("");

      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 403) {
          setInfoMessage(data.detail || "Please verify your email before logging in.");
          setView("verify");
          return;
        }
        throw new Error(data.detail || "Invalid email or password.");
      }

      localStorage.setItem("access_token", data.access_token);
      window.location.reload();
    } catch (error) {
      console.error(error);
      setLoginError(error.message);
    } finally {
      setLoggingIn(false);
    }
  }

  async function handleSignup(event) {
    event.preventDefault();

    try {
      setSigningUp(true);
      setSignupError("");

      const response = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ name, email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not create your account.");
      }

      setCode("");
      setVerifyError("");
      setInfoMessage(data.message || `We sent a verification code to ${email}.`);
      setView("verify");
    } catch (error) {
      console.error(error);
      setSignupError(error.message);
    } finally {
      setSigningUp(false);
    }
  }

  async function handleVerify(event) {
    event.preventDefault();

    try {
      setVerifying(true);
      setVerifyError("");

      const response = await fetch(`${API_URL}/auth/verify-email`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ email, code }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Invalid or expired code.");
      }

      localStorage.setItem("access_token", data.access_token);
      window.location.reload();
    } catch (error) {
      console.error(error);
      setVerifyError(error.message);
    } finally {
      setVerifying(false);
    }
  }

  async function handleResendCode() {
    try {
      setResending(true);
      setVerifyError("");

      const response = await fetch(`${API_URL}/auth/resend-code`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not resend the code.");
      }

      setInfoMessage(data.message || "A new code was sent to your email.");
    } catch (error) {
      console.error(error);
      setVerifyError(error.message);
    } finally {
      setResending(false);
    }
  }

  function goToView(nextView) {
    setLoginError("");
    setSignupError("");
    setVerifyError("");
    setInfoMessage("");
    setView(nextView);
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-icon"><BarChart3 size={24} /></div>
          <div>
            <h1>InsightFlow</h1>
            <p>Business Intelligence</p>
          </div>
        </div>

        {view === "login" && (
          <>
            <div className="login-heading">
              <p className="eyebrow">WELCOME BACK</p>
              <h2>Sign in to InsightFlow</h2>
              <p>Upload and analyze any business dataset.</p>
            </div>

            {loginError && <div className="login-error">{loginError}</div>}

            <form className="login-form" onSubmit={handleLogin}>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="Enter your email"
                  required
                />
              </div>

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </div>

              <button className="login-button" disabled={loggingIn}>
                {loggingIn ? "Signing in..." : "Sign In"}
              </button>
            </form>

            <p className="login-switch">
              Don't have an account?{" "}
              <button type="button" className="login-switch-link" onClick={() => goToView("signup")}>
                Create one
              </button>
            </p>
          </>
        )}

        {view === "signup" && (
          <>
            <div className="login-heading">
              <p className="eyebrow">GET STARTED</p>
              <h2>Create your account</h2>
              <p>We'll email you a verification code to confirm it's you.</p>
            </div>

            {signupError && <div className="login-error">{signupError}</div>}

            <form className="login-form" onSubmit={handleSignup}>
              <div className="form-group">
                <label>Full name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Enter your name"
                  minLength={2}
                  required
                />
              </div>

              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@gmail.com"
                  required
                />
              </div>

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  minLength={8}
                  required
                />
              </div>

              <button className="login-button" disabled={signingUp}>
                {signingUp ? "Creating account..." : "Create Account"}
              </button>
            </form>

            <p className="login-switch">
              Already have an account?{" "}
              <button type="button" className="login-switch-link" onClick={() => goToView("login")}>
                Sign in
              </button>
            </p>
          </>
        )}

        {view === "verify" && (
          <>
            <div className="login-heading">
              <p className="eyebrow">CHECK YOUR EMAIL</p>
              <h2>Enter verification code</h2>
              <p>{infoMessage || `We sent a 6-digit code to ${email || "your email"}.`}</p>
            </div>

            {verifyError && <div className="login-error">{verifyError}</div>}

            <form className="login-form" onSubmit={handleVerify}>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="Enter your email"
                  required
                />
              </div>

              <div className="form-group">
                <label>Verification code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  className="verification-code-input"
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="123456"
                  maxLength={6}
                  required
                />
              </div>

              <button className="login-button" disabled={verifying || code.length < 4}>
                {verifying ? "Verifying..." : "Verify & Continue"}
              </button>
            </form>

            <p className="login-switch">
              Didn't get a code?{" "}
              <button
                type="button"
                className="login-switch-link"
                onClick={handleResendCode}
                disabled={resending || !email}
              >
                {resending ? "Resending..." : "Resend code"}
              </button>
            </p>

            <p className="login-switch">
              <button type="button" className="login-switch-link" onClick={() => goToView("login")}>
                Back to sign in
              </button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
