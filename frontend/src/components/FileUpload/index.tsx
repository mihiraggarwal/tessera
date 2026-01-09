'use client';

import { useState, useCallback, useEffect } from 'react';
import { uploadApi, type Facility, type PDFExtractionResponse } from '@/lib/api';

interface FileUploadProps {
    onUploadSuccess: (facilities: Facility[], filename: string) => void;
    onUploadError?: (error: string) => void;
}

export default function FileUpload({ onUploadSuccess, onUploadError }: FileUploadProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
    const [facilityCount, setFacilityCount] = useState(0);
    const [availableFiles, setAvailableFiles] = useState<string[]>([]);
    const [pdfConfigured, setPdfConfigured] = useState<boolean | null>(null);
    const [pdfResult, setPdfResult] = useState<PDFExtractionResponse | null>(null);

    // Fetch available files and PDF status on mount
    useEffect(() => {
        uploadApi.getAvailableFiles()
            .then(setAvailableFiles)
            .catch((err) => console.error('Failed to load available files', err));

        uploadApi.getPdfExtractionStatus()
            .then((status) => setPdfConfigured(status.configured))
            .catch(() => setPdfConfigured(false));
    }, []);

    const handleFile = useCallback(async (file: File) => {
        const isPdf = file.name.toLowerCase().endsWith('.pdf');
        const isCsv = file.name.toLowerCase().endsWith('.csv');

        if (!isPdf && !isCsv) {
            onUploadError?.('Please upload a CSV or PDF file');
            return;
        }

        setIsUploading(true);

        try {
            if (isPdf) {
                // Handle PDF extraction
                const result = await uploadApi.extractPdf(file);

                if (result.success && result.tables.length > 0) {
                    setPdfResult(result);
                    setUploadedFileName(file.name);
                } else if (result.errors.length > 0) {
                    onUploadError?.(result.errors[0]);
                } else {
                    onUploadError?.('No tables found in PDF');
                }
            } else {
                // Handle CSV upload
                const result = await uploadApi.uploadCSV(file);

                if (result.success && result.facilities.length > 0) {
                    setUploadedFileName(file.name);
                    setFacilityCount(result.facilities.length);
                    onUploadSuccess(result.facilities, file.name);
                } else if (result.errors.length > 0) {
                    onUploadError?.(result.errors[0]);
                }
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Upload failed';
            onUploadError?.(message);
        } finally {
            setIsUploading(false);
        }
    }, [onUploadSuccess, onUploadError]);

    const handleLoadSampleData = useCallback(async () => {
        setIsUploading(true);

        try {
            const result = await uploadApi.getSampleData();

            if (result.success && result.facilities.length > 0) {
                setUploadedFileName('test.csv (sample)');
                setFacilityCount(result.facilities.length);
                onUploadSuccess(result.facilities, 'test.csv (sample)');
            } else {
                onUploadError?.('Failed to load sample data');
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to load sample data';
            onUploadError?.(message);
        } finally {
            setIsUploading(false);
        }
    }, [onUploadSuccess, onUploadError]);

    const handleLoadFile = useCallback(async (filename: string) => {
        if (!filename) return;

        setIsUploading(true);

        try {
            const result = await uploadApi.loadFile(filename);

            if (result.success && result.facilities.length > 0) {
                setUploadedFileName(filename);
                setFacilityCount(result.facilities.length);
                onUploadSuccess(result.facilities, filename);
            } else {
                onUploadError?.(`Failed to load ${filename}`);
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : `Failed to load ${filename}`;
            onUploadError?.(message);
        } finally {
            setIsUploading(false);
        }
    }, [onUploadSuccess, onUploadError]);

    const handleClear = useCallback(() => {
        setUploadedFileName(null);
        setFacilityCount(0);
        setPdfResult(null);
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const file = e.dataTransfer.files[0];
        if (file) {
            handleFile(file);
        }
    }, [handleFile]);

    const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            handleFile(file);
        }
    }, [handleFile]);

    // Show PDF extraction preview
    if (pdfResult && uploadedFileName) {
        return (
            <div className="w-full space-y-4">
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                                <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                            </div>
                            <div>
                                <p className="font-medium text-purple-800">{uploadedFileName}</p>
                                <p className="text-sm text-purple-600">
                                    {pdfResult.table_count} table(s) found across {pdfResult.page_count} page(s)
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={handleClear}
                            className="text-gray-500 hover:text-gray-700 p-2 hover:bg-purple-100 rounded-lg transition-colors"
                            title="Clear and upload new file"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {/* Table Preview */}
                    {pdfResult.tables.length > 0 && (
                        <div className="mt-4 bg-white rounded-lg border border-purple-100 overflow-hidden">
                            <div className="px-3 py-2 bg-purple-100 text-purple-800 text-sm font-medium">
                                Extracted Table Preview (first 5 rows)
                            </div>
                            <div className="overflow-x-auto max-h-48">
                                <table className="w-full text-xs">
                                    <thead className="bg-gray-50 sticky top-0">
                                        <tr>
                                            {pdfResult.tables[0].headers.map((h, i) => (
                                                <th key={i} className="px-2 py-1 text-left text-gray-600 font-medium border-b">
                                                    {h}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {pdfResult.tables[0].rows.slice(0, 5).map((row, i) => (
                                            <tr key={i} className="border-b border-gray-100">
                                                {pdfResult.tables[0].headers.map((h, j) => (
                                                    <td key={j} className="px-2 py-1 text-gray-700">
                                                        {row[h] || '-'}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Mapped Data Info */}
                    {pdfResult.mapped_data.length > 0 && (
                        <div className="mt-3 p-2 bg-green-50 rounded-lg text-sm text-green-700">
                            ✓ {pdfResult.mapped_data.length} rows mapped to population schema
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Show uploaded file info
    if (uploadedFileName && !pdfResult) {
        return (
            <div className="w-full">
                <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <div>
                                <p className="font-medium text-green-800">{uploadedFileName}</p>
                                <p className="text-sm text-green-600">{facilityCount} facilities loaded</p>
                            </div>
                        </div>
                        <button
                            onClick={handleClear}
                            className="text-gray-500 hover:text-gray-700 p-2 hover:bg-green-100 rounded-lg transition-colors"
                            title="Clear and upload new file"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full space-y-3">
            {/* Drop Zone */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
                    relative border-2 border-dashed rounded-xl p-6 text-center
                    transition-all duration-200 cursor-pointer
                    ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400 bg-white'}
                    ${isUploading ? 'opacity-50 pointer-events-none' : ''}
                `}
            >
                <input
                    type="file"
                    accept=".csv,.pdf"
                    onChange={handleFileInput}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={isUploading}
                />

                <div className="space-y-2">
                    <div className="mx-auto w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                        <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                    </div>

                    <div>
                        <p className="text-gray-700 font-medium text-sm">
                            {isUploading ? 'Loading...' : 'Drop CSV or PDF file'}
                        </p>
                        {pdfConfigured && (
                            <p className="text-xs text-gray-500 mt-1">PDF tables will be auto-extracted</p>
                        )}
                    </div>
                </div>
            </div>

            {/* Available Files Dropdown */}
            {availableFiles.length > 0 && (
                <div>
                    <label className="block text-sm text-gray-600 mb-1">Or select from available datasets:</label>
                    <select
                        onChange={(e) => handleLoadFile(e.target.value)}
                        disabled={isUploading}
                        defaultValue=""
                        className="w-full py-2 px-3 bg-gray-50 border border-gray-300 text-gray-700 rounded-lg text-sm focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                    >
                        <option value="" disabled>Select a file...</option>
                        {availableFiles.map(file => (
                            <option key={file} value={file}>{file}</option>
                        ))}
                    </select>
                </div>
            )}

            {/* Sample Data Button */}
            <button
                onClick={handleLoadSampleData}
                disabled={isUploading}
                className="w-full py-2 px-4 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
                {isUploading ? 'Loading...' : 'Use Sample Data (test.csv)'}
            </button>
        </div>
    );
}
