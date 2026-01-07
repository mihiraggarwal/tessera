'use client';

import { useState, useCallback } from 'react';
import { uploadApi, type Facility, type UploadResponse } from '@/lib/api';

interface FileUploadProps {
    onUploadSuccess: (facilities: Facility[]) => void;
    onUploadError?: (error: string) => void;
}

export default function FileUpload({ onUploadSuccess, onUploadError }: FileUploadProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

    const handleFile = useCallback(async (file: File) => {
        if (!file.name.endsWith('.csv')) {
            onUploadError?.('Please upload a CSV file');
            return;
        }

        setIsUploading(true);
        setUploadResult(null);

        try {
            const result = await uploadApi.uploadCSV(file);
            setUploadResult(result);

            if (result.success && result.facilities.length > 0) {
                onUploadSuccess(result.facilities);
            } else if (result.errors.length > 0) {
                onUploadError?.(result.errors[0]);
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Upload failed';
            onUploadError?.(message);
        } finally {
            setIsUploading(false);
        }
    }, [onUploadSuccess, onUploadError]);

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

    return (
        <div className="w-full">
            {/* Drop Zone */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
          relative border-2 border-dashed rounded-xl p-8 text-center
          transition-all duration-200 cursor-pointer
          ${isDragging
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400 bg-white'
                    }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
            >
                <input
                    type="file"
                    accept=".csv"
                    onChange={handleFileInput}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={isUploading}
                />

                <div className="space-y-3">
                    <div className="mx-auto w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                        <svg
                            className="w-6 h-6 text-blue-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                            />
                        </svg>
                    </div>

                    <div>
                        <p className="text-gray-700 font-medium">
                            {isUploading ? 'Uploading...' : 'Drop CSV file here or click to browse'}
                        </p>
                        <p className="text-gray-500 text-sm mt-1">
                            CSV with columns: name, latitude, longitude
                        </p>
                    </div>
                </div>
            </div>

            {/* Upload Result */}
            {uploadResult && (
                <div className={`mt-4 p-4 rounded-lg ${uploadResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
                    <div className="flex items-start gap-3">
                        <div className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${uploadResult.success ? 'bg-green-500' : 'bg-red-500'}`}>
                            {uploadResult.success ? (
                                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                </svg>
                            ) : (
                                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            )}
                        </div>
                        <div className="flex-1">
                            <p className={`font-medium ${uploadResult.success ? 'text-green-800' : 'text-red-800'}`}>
                                {uploadResult.success
                                    ? `Loaded ${uploadResult.valid_facilities} facilities`
                                    : 'Upload failed'
                                }
                            </p>
                            {uploadResult.errors.length > 0 && (
                                <ul className="mt-2 text-sm text-red-700 list-disc list-inside">
                                    {uploadResult.errors.slice(0, 3).map((error, i) => (
                                        <li key={i}>{error}</li>
                                    ))}
                                    {uploadResult.errors.length > 3 && (
                                        <li>...and {uploadResult.errors.length - 3} more errors</li>
                                    )}
                                </ul>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
