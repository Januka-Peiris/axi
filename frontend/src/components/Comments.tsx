import { useState, useEffect } from 'react';
import { MessageSquare, Send, User, Clock, Trash2, Edit2, X, Check } from 'lucide-react';

interface Comment {
    id: string;
    text: string;
    author: string;
    createdAt: Date;
    updatedAt?: Date;
}

interface CommentsProps {
    entityType: 'metric' | 'dimension' | 'entity';
    entityId: string;
}

// Local storage key for comments
const getStorageKey = (entityType: string, entityId: string) =>
    `axi_comments_${entityType}_${entityId}`;

export const Comments = ({ entityType, entityId }: CommentsProps) => {
    const [comments, setComments] = useState<Comment[]>([]);
    const [newComment, setNewComment] = useState('');
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editText, setEditText] = useState('');

    // Load comments from local storage
    useEffect(() => {
        const key = getStorageKey(entityType, entityId);
        const stored = localStorage.getItem(key);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                setComments(parsed.map((c: any) => ({
                    ...c,
                    createdAt: new Date(c.createdAt),
                    updatedAt: c.updatedAt ? new Date(c.updatedAt) : undefined
                })));
            } catch {
                setComments([]);
            }
        }
    }, [entityType, entityId]);

    // Save comments to local storage
    const saveComments = (newComments: Comment[]) => {
        const key = getStorageKey(entityType, entityId);
        localStorage.setItem(key, JSON.stringify(newComments));
        setComments(newComments);
    };

    const handleAddComment = () => {
        if (!newComment.trim()) return;

        const comment: Comment = {
            id: `comment_${Date.now()}`,
            text: newComment.trim(),
            author: 'You', // In a real app, this would come from auth
            createdAt: new Date()
        };

        saveComments([comment, ...comments]);
        setNewComment('');
    };

    const handleDeleteComment = (id: string) => {
        saveComments(comments.filter(c => c.id !== id));
    };

    const handleEditComment = (id: string) => {
        const comment = comments.find(c => c.id === id);
        if (comment) {
            setEditingId(id);
            setEditText(comment.text);
        }
    };

    const handleSaveEdit = () => {
        if (!editText.trim() || !editingId) return;

        saveComments(comments.map(c =>
            c.id === editingId
                ? { ...c, text: editText.trim(), updatedAt: new Date() }
                : c
        ));
        setEditingId(null);
        setEditText('');
    };

    const handleCancelEdit = () => {
        setEditingId(null);
        setEditText('');
    };

    const formatDate = (date: Date) => {
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        return date.toLocaleDateString();
    };

    return (
        <div className="rounded-xl border border-white/10 bg-[#151821]">
            {/* Header */}
            <div className="flex items-center gap-2 p-4 border-b border-white/10">
                <MessageSquare className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                    Comments
                </h3>
                <span className="text-xs text-slate-500">({comments.length})</span>
            </div>

            {/* Add Comment */}
            <div className="p-4 border-b border-white/10">
                <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                        <User className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div className="flex-1">
                        <textarea
                            value={newComment}
                            onChange={(e) => setNewComment(e.target.value)}
                            placeholder="Add a comment..."
                            rows={2}
                            className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 resize-none focus:outline-none focus:border-cyan-500"
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && e.metaKey) {
                                    handleAddComment();
                                }
                            }}
                        />
                        <div className="flex justify-between items-center mt-2">
                            <span className="text-xs text-slate-500">Cmd+Enter to submit</span>
                            <button
                                onClick={handleAddComment}
                                disabled={!newComment.trim()}
                                className="flex items-center gap-1 px-3 py-1.5 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-sm rounded-lg transition-colors"
                            >
                                <Send className="w-4 h-4" />
                                Post
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Comments List */}
            <div className="divide-y divide-white/5 max-h-[400px] overflow-y-auto">
                {comments.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">
                        <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>No comments yet. Be the first to comment!</p>
                    </div>
                ) : (
                    comments.map(comment => (
                        <div key={comment.id} className="p-4 hover:bg-white/5 transition-colors">
                            <div className="flex gap-3">
                                <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                                    <User className="w-4 h-4 text-purple-400" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-medium text-white">
                                            {comment.author}
                                        </span>
                                        <span className="flex items-center gap-1 text-xs text-slate-500">
                                            <Clock className="w-3 h-3" />
                                            {formatDate(comment.createdAt)}
                                        </span>
                                        {comment.updatedAt && (
                                            <span className="text-xs text-slate-600">(edited)</span>
                                        )}
                                    </div>

                                    {editingId === comment.id ? (
                                        <div>
                                            <textarea
                                                value={editText}
                                                onChange={(e) => setEditText(e.target.value)}
                                                rows={2}
                                                className="w-full bg-black/30 border border-cyan-500/50 rounded-lg px-3 py-2 text-sm text-white resize-none focus:outline-none"
                                                autoFocus
                                            />
                                            <div className="flex gap-2 mt-2">
                                                <button
                                                    onClick={handleSaveEdit}
                                                    className="flex items-center gap-1 px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded hover:bg-green-500/30"
                                                >
                                                    <Check className="w-3 h-3" />
                                                    Save
                                                </button>
                                                <button
                                                    onClick={handleCancelEdit}
                                                    className="flex items-center gap-1 px-2 py-1 bg-white/5 text-slate-400 text-xs rounded hover:bg-white/10"
                                                >
                                                    <X className="w-3 h-3" />
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <>
                                            <p className="text-sm text-slate-300 whitespace-pre-wrap break-words">
                                                {comment.text}
                                            </p>
                                            <div className="flex gap-2 mt-2">
                                                <button
                                                    onClick={() => handleEditComment(comment.id)}
                                                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-cyan-400"
                                                >
                                                    <Edit2 className="w-3 h-3" />
                                                    Edit
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteComment(comment.id)}
                                                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-red-400"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                    Delete
                                                </button>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default Comments;
