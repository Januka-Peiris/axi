import { useState } from 'react';
import { Rocket, Database, CheckCircle, Copy, ExternalLink } from 'lucide-react';

interface Step {
    id: number;
    title: string;
    description: string;
    command?: string;
    completed?: boolean;
}

const STEPS: Step[] = [
    {
        id: 1,
        title: "Generate Demo Project",
        description: "Create a sample e-commerce project with models, metrics, and dimensions.",
        command: "axi demo --output ./my_project"
    },
    {
        id: 2,
        title: "Navigate to Project",
        description: "Change to your project directory.",
        command: "cd ./my_project"
    },
    {
        id: 3,
        title: "Start the UI",
        description: "Launch the AXI web interface.",
        command: "axi ui"
    },
    {
        id: 4,
        title: "Explore Your Data",
        description: "Browse metrics, dimensions, and run semantic queries.",
    }
];

const CodeBlock = ({ code }: { code: string }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="flex items-center gap-2 bg-black/40 rounded-lg px-3 py-2 font-mono text-sm">
            <code className="flex-1 text-cyan-400">{code}</code>
            <button
                onClick={handleCopy}
                className="p-1 hover:bg-white/10 rounded transition-colors"
                title="Copy to clipboard"
            >
                {copied ? (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                    <Copy className="w-4 h-4 text-slate-400" />
                )}
            </button>
        </div>
    );
};

export const Onboarding = ({ onDismiss }: { onDismiss?: () => void }) => {
    const [currentStep, setCurrentStep] = useState(0);

    return (
        <div className="max-w-2xl mx-auto">
            <div className="card border-cyan-500/30 bg-gradient-to-br from-[#151821] to-[#1a1f2e]">
                {/* Header */}
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-3 bg-cyan-500/10 rounded-xl">
                        <Rocket className="w-6 h-6 text-cyan-400" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold">Welcome to AXI</h2>
                        <p className="text-sm text-slate-400">Get started in 4 easy steps</p>
                    </div>
                </div>

                {/* Steps */}
                <div className="space-y-4">
                    {STEPS.map((step, index) => (
                        <div
                            key={step.id}
                            className={`p-4 rounded-lg border transition-all cursor-pointer ${
                                index === currentStep
                                    ? 'border-cyan-500/50 bg-cyan-500/5'
                                    : index < currentStep
                                    ? 'border-green-500/30 bg-green-500/5'
                                    : 'border-white/5 bg-white/5 opacity-60'
                            }`}
                            onClick={() => setCurrentStep(index)}
                        >
                            <div className="flex items-start gap-3">
                                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                                    index < currentStep
                                        ? 'bg-green-500 text-white'
                                        : index === currentStep
                                        ? 'bg-cyan-500 text-white'
                                        : 'bg-white/10 text-slate-400'
                                }`}>
                                    {index < currentStep ? <CheckCircle className="w-4 h-4" /> : step.id}
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-medium mb-1">{step.title}</h3>
                                    <p className="text-sm text-slate-400 mb-2">{step.description}</p>
                                    {step.command && index === currentStep && (
                                        <CodeBlock code={step.command} />
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Navigation */}
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-white/10">
                    <button
                        onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
                        disabled={currentStep === 0}
                        className="px-4 py-2 text-sm text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        Previous
                    </button>

                    <div className="flex items-center gap-2">
                        {STEPS.map((_, index) => (
                            <div
                                key={index}
                                className={`w-2 h-2 rounded-full transition-colors ${
                                    index === currentStep ? 'bg-cyan-500' : 'bg-white/20'
                                }`}
                            />
                        ))}
                    </div>

                    {currentStep < STEPS.length - 1 ? (
                        <button
                            onClick={() => setCurrentStep(currentStep + 1)}
                            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white text-sm rounded-lg transition-colors"
                        >
                            Next
                        </button>
                    ) : (
                        <button
                            onClick={onDismiss}
                            className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm rounded-lg transition-colors"
                        >
                            Get Started
                        </button>
                    )}
                </div>

                {/* Quick Links */}
                <div className="mt-6 pt-4 border-t border-white/10">
                    <p className="text-xs text-slate-500 mb-2">Resources</p>
                    <div className="flex gap-4">
                        <a href="#/docs" className="flex items-center gap-1 text-sm text-cyan-400 hover:text-cyan-300">
                            <Database className="w-4 h-4" /> Documentation
                        </a>
                        <a href="https://github.com/mshdata/axi" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-sm text-slate-400 hover:text-white">
                            <ExternalLink className="w-4 h-4" /> GitHub
                        </a>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Onboarding;
