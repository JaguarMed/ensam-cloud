"""
Script Analyzer Service - Automatic Resource Allocation

Analyzes Python scripts to determine optimal resource profile:
- Detects GPU-requiring libraries (torch, tensorflow, cuda)
- Detects memory-intensive libraries (pandas, numpy, scipy)
- Detects long-running patterns (training loops, large iterations)
- Checks current system resources availability
"""

import re
import logging
from typing import Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceLevel(Enum):
    """Resource requirement levels."""
    MINIMAL = "small"
    STANDARD = "medium"
    INTENSIVE = "large"
    GPU_REQUIRED = "gpu"


@dataclass
class ScriptAnalysis:
    """Result of script analysis."""
    recommended_profile: str
    execution_mode: str  # "cpu" or "gpu"
    detected_libraries: List[str]
    gpu_indicators: List[str]
    memory_indicators: List[str]
    compute_indicators: List[str]
    confidence: float  # 0.0 to 1.0
    reasoning: str


# Libraries that require GPU
GPU_LIBRARIES = {
    'torch': 'PyTorch deep learning',
    'tensorflow': 'TensorFlow deep learning',
    'keras': 'Keras neural networks',
    'cupy': 'CUDA-accelerated NumPy',
    'cudf': 'CUDA DataFrame',
    'cuml': 'CUDA Machine Learning',
    'pycuda': 'Python CUDA bindings',
    'numba': 'JIT compiler (may use GPU)',
    'jax': 'JAX accelerated computing',
    'mxnet': 'MXNet deep learning',
    'paddle': 'PaddlePaddle deep learning',
    'onnxruntime': 'ONNX Runtime (may use GPU)',
}

# Libraries that are memory-intensive
MEMORY_INTENSIVE_LIBRARIES = {
    'pandas': 'DataFrame operations',
    'numpy': 'Numerical computing',
    'scipy': 'Scientific computing',
    'sklearn': 'Machine Learning',
    'scikit-learn': 'Machine Learning',
    'xgboost': 'Gradient Boosting',
    'lightgbm': 'Light Gradient Boosting',
    'catboost': 'CatBoost',
    'dask': 'Parallel computing',
    'polars': 'Fast DataFrame',
    'vaex': 'Out-of-core DataFrames',
    'modin': 'Parallel Pandas',
    'opencv': 'Computer Vision',
    'cv2': 'OpenCV',
    'PIL': 'Image Processing',
    'pillow': 'Image Processing',
    'matplotlib': 'Plotting (memory for figures)',
    'seaborn': 'Statistical visualization',
    'plotly': 'Interactive plots',
}

# Patterns indicating heavy computation
COMPUTE_INTENSIVE_PATTERNS = [
    (r'\.fit\s*\(', 'Model training detected'),
    (r'\.train\s*\(', 'Training loop detected'),
    (r'for\s+epoch\s+in', 'Epoch loop detected'),
    (r'for\s+\w+\s+in\s+range\s*\(\s*\d{4,}', 'Large iteration loop'),
    (r'while\s+True', 'Infinite loop pattern'),
    (r'\.cuda\s*\(', 'CUDA tensor transfer'),
    (r'\.to\s*\(\s*[\'"]cuda', 'CUDA device transfer'),
    (r'torch\.device\s*\(\s*[\'"]cuda', 'CUDA device creation'),
    (r'with\s+tf\.device.*GPU', 'TensorFlow GPU context'),
    (r'model\.compile', 'Keras model compilation'),
    (r'DataLoader', 'PyTorch DataLoader'),
    (r'tf\.data\.Dataset', 'TensorFlow Dataset'),
    (r'\.backward\s*\(', 'Backpropagation'),
    (r'optimizer\.step', 'Optimizer step'),
    (r'\.predict\s*\(', 'Model prediction'),
    (r'\.transform\s*\(', 'Data transformation'),
    (r'multiprocessing', 'Multiprocessing'),
    (r'ThreadPoolExecutor', 'Thread pool'),
    (r'ProcessPoolExecutor', 'Process pool'),
]

# Patterns indicating GPU usage
GPU_USAGE_PATTERNS = [
    (r'\.cuda\s*\(', 'CUDA transfer'),
    (r'\.to\s*\(\s*[\'"]cuda', 'To CUDA device'),
    (r'torch\.cuda', 'PyTorch CUDA'),
    (r'tf\.config.*GPU', 'TensorFlow GPU config'),
    (r'with\s+tf\.device.*GPU', 'TensorFlow GPU device'),
    (r'gpu_options', 'GPU options'),
    (r'CUDA_VISIBLE_DEVICES', 'CUDA environment'),
    (r'cupy\.', 'CuPy operations'),
    (r'@cuda\.jit', 'Numba CUDA JIT'),
    (r'device\s*=\s*[\'"]cuda', 'CUDA device assignment'),
]


class ScriptAnalyzer:
    """
    Analyzes Python scripts to recommend optimal resource allocation.
    """
    
    def __init__(self, gpu_available: bool = False):
        self.gpu_available = gpu_available
    
    def analyze(self, script_content: str) -> ScriptAnalysis:
        """
        Analyze a Python script and recommend resources.
        
        Args:
            script_content: The Python source code to analyze
            
        Returns:
            ScriptAnalysis with recommendations
        """
        if not script_content or not script_content.strip():
            return ScriptAnalysis(
                recommended_profile="small",
                execution_mode="cpu",
                detected_libraries=[],
                gpu_indicators=[],
                memory_indicators=[],
                compute_indicators=[],
                confidence=1.0,
                reasoning="Empty or minimal script - using small profile"
            )
        
        # Extract imports
        detected_libs = self._detect_libraries(script_content)
        
        # Check for GPU indicators
        gpu_indicators = self._detect_gpu_usage(script_content, detected_libs)
        
        # Check for memory-intensive operations
        memory_indicators = self._detect_memory_usage(detected_libs)
        
        # Check for compute-intensive patterns
        compute_indicators = self._detect_compute_patterns(script_content)
        
        # Determine profile and mode
        profile, mode, confidence, reasoning = self._determine_profile(
            detected_libs,
            gpu_indicators,
            memory_indicators,
            compute_indicators
        )
        
        # If GPU not available but recommended, fallback to CPU
        if mode == "gpu" and not self.gpu_available:
            mode = "cpu"
            if profile == "gpu":
                profile = "large"
            reasoning += " (GPU not available, using CPU fallback)"
        
        return ScriptAnalysis(
            recommended_profile=profile,
            execution_mode=mode,
            detected_libraries=detected_libs,
            gpu_indicators=gpu_indicators,
            memory_indicators=memory_indicators,
            compute_indicators=compute_indicators,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def _detect_libraries(self, script: str) -> List[str]:
        """Detect imported libraries in the script."""
        detected = []
        
        # Match import statements
        import_patterns = [
            r'^import\s+(\w+)',           # import x
            r'^from\s+(\w+)',             # from x import y
            r'^import\s+(\w+)\s+as',      # import x as y
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, script, re.MULTILINE)
            detected.extend(matches)
        
        # Also check for common library usage without explicit import
        for lib in list(GPU_LIBRARIES.keys()) + list(MEMORY_INTENSIVE_LIBRARIES.keys()):
            if lib + '.' in script or lib + '(' in script:
                if lib not in detected:
                    detected.append(lib)
        
        return list(set(detected))
    
    def _detect_gpu_usage(self, script: str, libraries: List[str]) -> List[str]:
        """Detect GPU usage indicators."""
        indicators = []
        
        # Check for GPU libraries
        for lib in libraries:
            if lib in GPU_LIBRARIES:
                indicators.append(f"Library: {lib} ({GPU_LIBRARIES[lib]})")
        
        # Check for GPU patterns
        for pattern, description in GPU_USAGE_PATTERNS:
            if re.search(pattern, script, re.IGNORECASE):
                indicators.append(f"Pattern: {description}")
        
        return list(set(indicators))
    
    def _detect_memory_usage(self, libraries: List[str]) -> List[str]:
        """Detect memory-intensive library usage."""
        indicators = []
        
        for lib in libraries:
            if lib in MEMORY_INTENSIVE_LIBRARIES:
                indicators.append(f"{lib} ({MEMORY_INTENSIVE_LIBRARIES[lib]})")
        
        return indicators
    
    def _detect_compute_patterns(self, script: str) -> List[str]:
        """Detect compute-intensive patterns."""
        indicators = []
        
        for pattern, description in COMPUTE_INTENSIVE_PATTERNS:
            if re.search(pattern, script, re.IGNORECASE):
                indicators.append(description)
        
        return list(set(indicators))
    
    def _determine_profile(
        self,
        libraries: List[str],
        gpu_indicators: List[str],
        memory_indicators: List[str],
        compute_indicators: List[str]
    ) -> Tuple[str, str, float, str]:
        """
        Determine the optimal profile based on analysis.
        
        Returns:
            (profile, execution_mode, confidence, reasoning)
        """
        reasoning_parts = []
        
        # Score calculation
        gpu_score = len(gpu_indicators) * 3
        memory_score = len(memory_indicators) * 2
        compute_score = len(compute_indicators) * 2
        
        total_score = gpu_score + memory_score + compute_score
        
        # Determine execution mode
        if gpu_score >= 3:
            execution_mode = "gpu"
            reasoning_parts.append(f"GPU recommended ({len(gpu_indicators)} GPU indicators)")
        else:
            execution_mode = "cpu"
        
        # Determine profile
        if gpu_score >= 3:
            profile = "gpu"
            confidence = min(0.9, 0.5 + gpu_score * 0.1)
            reasoning_parts.append("Using GPU profile for deep learning workload")
        elif total_score >= 8:
            profile = "large"
            confidence = min(0.85, 0.5 + total_score * 0.05)
            reasoning_parts.append("Heavy computation detected - using large profile")
        elif total_score >= 4:
            profile = "medium"
            confidence = min(0.8, 0.5 + total_score * 0.05)
            reasoning_parts.append("Moderate resource needs - using medium profile")
        elif memory_score >= 2:
            profile = "medium"
            confidence = 0.7
            reasoning_parts.append("Memory-intensive libraries detected")
        else:
            profile = "small"
            confidence = 0.8
            reasoning_parts.append("Simple script - using small profile")
        
        # Add library info to reasoning
        if libraries:
            lib_names = libraries[:5]  # First 5
            if len(libraries) > 5:
                lib_names.append(f"...and {len(libraries) - 5} more")
            reasoning_parts.append(f"Detected: {', '.join(lib_names)}")
        
        reasoning = ". ".join(reasoning_parts)
        
        return profile, execution_mode, confidence, reasoning


def analyze_script(script_content: str, gpu_available: bool = False) -> ScriptAnalysis:
    """
    Convenience function to analyze a script.
    
    Args:
        script_content: Python source code
        gpu_available: Whether GPU is available on the system
        
    Returns:
        ScriptAnalysis with recommendations
    """
    analyzer = ScriptAnalyzer(gpu_available=gpu_available)
    return analyzer.analyze(script_content)


def get_auto_profile(script_content: str, gpu_available: bool = False) -> Tuple[str, str]:
    """
    Quick function to get just the profile and mode.
    
    Args:
        script_content: Python source code
        gpu_available: Whether GPU is available
        
    Returns:
        (resource_profile, execution_mode) tuple
    """
    analysis = analyze_script(script_content, gpu_available)
    return analysis.recommended_profile, analysis.execution_mode







