// src/pages/Library.tsx
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
    BookOpen, Film, Upload, Search, Music, LogOut, UserPlus, Loader2, X,
} from "lucide-react";

import { Book, Video, Audio, Tag as TagType } from "../types";
import * as booksApi from "../services/api/books";
import { pageCount } from "../services/api/paging";
import { useVideos } from "../hooks/useVideos";
import { useAudio } from "../hooks/useAudio";
import { useBookSearch } from "../hooks/useBookSearch";

import { TagDropdown } from "../components/shared/TagDropdown";
import { EmptyState } from "../components/shared/EmptyState";
import { UploadModal, UploadKind } from "../components/shared/UploadModal";
import { AddTeacherModal } from "../components/auth/AddTeacherModal";
import { ChangePasswordModal } from "../components/auth/ChangePasswordModal";
import { BookEditModal } from "../components/books/BookEditModal";
import { BookGridCard } from "../components/books/BookGridCard";
import { VideoGridCard } from "../components/video/VideoGridCard";
import { VideoPlayerModal } from "../components/video/VideoPlayerModal";
import { AudioGridCard } from "../components/audio/AudioGridCard";

type TabId = "books" | "audio" | "videos";

const uniqueTags = (items: { tags?: TagType[] }[]): TagType[] => [
    ...new Map(items.flatMap(item => item.tags || []).map(tag => [tag.name, tag])).values(),
];

const toggled = (selected: string[], tag: string): string[] =>
    selected.includes(tag) ? selected.filter(t => t !== tag) : [...selected, tag];

const pagerButton =
    "px-3 py-1.5 rounded-lg border border-[#E8E4DE] bg-white text-[#6B6560] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed";

const Library = () => {
    const { isAdmin, isTeacher, logout, auth, markPasswordChanged } = useAuth();
    const navigate = useNavigate();
    // The API lets admins and teachers add, edit and delete content; only an
    // admin may create teacher accounts.
    const canManage = isAdmin || isTeacher;

    const isMobile = window.innerWidth < 640;

    const [activeTab, setActiveTab] = useState<TabId>("books");
    const [search, setSearch] = useState("");
    const [bookPage, setBookPage] = useState(1);
    const [selectedBookTags, setSelectedBookTags] = useState<string[]>([]);
    const [selectedVideoTags, setSelectedVideoTags] = useState<string[]>([]);
    const [selectedAudioTags, setSelectedAudioTags] = useState<string[]>([]);
    const [showUpload, setShowUpload] = useState(false);
    const [editingBook, setEditingBook] = useState<Book | null>(null);
    const [currentlyPlayingAudio, setCurrentlyPlayingAudio] = useState<Audio["id"] | null>(null);
    const [playingVideo, setPlayingVideo] = useState<Video | null>(null);
    const [showAddTeacher, setShowAddTeacher] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);

    // Books support real server-side search/tag filtering, one page at a time.
    const {
        books, total: bookTotal, loading: booksLoading, error: booksError, refresh: refreshBooks,
    } = useBookSearch(selectedBookTags, search, bookPage);
    // Videos/audio have no search endpoint — fetch the full list, filter client-side below.
    const { videos, loading: videosLoading, error: videosError, refresh: refreshVideos, setVideos } = useVideos();
    const { audioTracks, loading: audioLoading, error: audioError, refresh: refreshAudio, setAudioTracks } = useAudio();

    // Each hook loads its own list on mount; this is only the first-paint spinner.
    const loading = booksLoading || videosLoading || audioLoading;
    const tabError = activeTab === "books" ? booksError : activeTab === "audio" ? audioError : videosError;

    const bookPages = pageCount(bookTotal);
    useEffect(() => {
        // Deleting the last book of the last page leaves that page empty.
        if (bookPage > bookPages) setBookPage(bookPages);
    }, [bookPage, bookPages]);

    // Unique book tags come from the unfiltered set, so they don't shrink as filters narrow the list.
    const [bookTagsList, setBookTagsList] = useState<TagType[]>([]);
    const refreshBookTags = async () => {
        try {
            const page = await booksApi.searchBooks();
            setBookTagsList(uniqueTags(page.items));
        } catch {
            // The filter keeps its previous options; the book list itself reports load failures.
        }
    };
    useEffect(() => {
        refreshBookTags();
    }, []);

    const filteredVideos = useMemo(() => videos.filter(v =>
        v.title.toLowerCase().includes(search.toLowerCase()) &&
        (selectedVideoTags.length === 0 || v.tags?.some(t => selectedVideoTags.includes(t.name)))
    ), [videos, search, selectedVideoTags]);

    const filteredAudio = useMemo(() => audioTracks.filter(a =>
        a.title.toLowerCase().includes(search.toLowerCase()) &&
        (selectedAudioTags.length === 0 || a.tags?.some(t => selectedAudioTags.includes(t.name)))
    ), [audioTracks, search, selectedAudioTags]);

    const videoTagsList = useMemo(() => uniqueTags(videos), [videos]);
    const audioTagsList = useMemo(() => uniqueTags(audioTracks), [audioTracks]);

    const handleLogout = () => { logout(); navigate("/"); };
    const uploadType: UploadKind = activeTab === "books" ? "book" : activeTab === "audio" ? "audio" : "video";
    const roleLabel = isAdmin ? "Admin" : isTeacher ? "Teacher" : "Student";

    // A new query starts again from the first page of its results.
    const changeSearch = (value: string) => { setSearch(value); setBookPage(1); };
    const changeBookTags = (next: string[]) => { setSelectedBookTags(next); setBookPage(1); };
    const switchTab = (id: TabId) => {
        setActiveTab(id);
        setSelectedBookTags([]); setSelectedVideoTags([]); setSelectedAudioTags([]);
        setSearch(""); setBookPage(1);
    };
    const refreshAfterBookChange = () => { refreshBooks(); refreshBookTags(); };

    const tabs: { id: TabId; label: string; icon: typeof BookOpen; count: number }[] = [
        { id: "books", label: "Books", icon: BookOpen, count: bookTotal },
        { id: "audio", label: "Audio", icon: Music, count: audioTracks.length },
        { id: "videos", label: "Videos", icon: Film, count: videos.length },
    ];

    return (
        <div className="flex h-screen bg-white font-sans overflow-hidden">

            {/* SIDEBAR */}
            <aside className={`${isMobile ? "w-[58px]" : "w-[220px]"} flex-shrink-0 bg-white border-r border-[#E8E4DE] flex flex-col`}>
                <div className={`${isMobile ? "py-3.5 justify-center" : "pt-6 px-5 pb-5 justify-start"} border-b border-[#E8E4DE] flex items-center`}>
                    {isMobile
                        ? <BookOpen size={20} color="#B8922A" />
                        : <div>
                            <h1 className="text-[21px] font-bold text-[#1C1A17] m-0 tracking-[-0.01em]">Jirani</h1>
                            <p className="text-[10px] text-[#A09890] mt-1 mb-0 uppercase tracking-[0.08em] font-semibold">Offline Library</p>
                        </div>
                    }
                </div>

                <nav className={isMobile ? "py-2.5 px-1.5" : "py-3 px-2.5"}>
                    {tabs.map(({ id, label, icon: Icon, count }) => (
                        <button key={id}
                            onClick={() => switchTab(id)}
                            className={`w-full flex items-center ${isMobile ? "justify-center flex-col gap-0.5 py-2" : "justify-between flex-row gap-2 py-2.5 px-3"} rounded-[10px] border-none cursor-pointer mb-0.5 text-[13px] transition-colors ${activeTab === id ? "bg-[#F5EDD8] text-[#B8922A] font-bold" : "bg-transparent text-[#6B6560] font-normal"}`}>
                            {isMobile
                                ? <>
                                    <Icon size={20} />
                                    <span className={`text-[9px] font-semibold ${activeTab === id ? "text-[#B8922A]" : "text-[#A09890]"}`}>{count}</span>
                                </>
                                : <>
                                    <div className="flex items-center gap-2">
                                        <Icon size={15} />
                                        <span>{label}</span>
                                    </div>
                                    <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${activeTab === id ? "bg-[#B8922A] text-white" : "bg-[#F0EDE8] text-[#A09890]"}`}>
                                        {count}
                                    </span>
                                </>
                            }
                        </button>
                    ))}
                </nav>

                <div className={`mt-auto ${isMobile ? "py-2.5 px-1.5" : "py-3 px-2.5"} border-t border-[#E8E4DE] flex flex-col gap-1.5`}>
                    {isAdmin && (
                        <button onClick={() => setShowAddTeacher(true)}
                            aria-label="Add Teacher"
                            className={`w-full flex items-center ${isMobile ? "justify-center py-2" : "justify-start py-2 px-3"} gap-2 rounded-[10px] border border-dashed border-[#D4A93A] bg-transparent hover:bg-[#F5EDD8] text-[#B8922A] cursor-pointer text-xs font-semibold transition-colors`}>
                            <UserPlus size={isMobile ? 18 : 13} />
                            {!isMobile && "Add Teacher"}
                        </button>
                    )}
                    <div className={`${isMobile ? "py-2 justify-center" : "py-2 px-3 justify-between"} rounded-[10px] bg-[#FAFAF9] flex items-center gap-2`}>
                        {!isMobile && (
                            <div className="min-w-0">
                                <p className="text-xs font-semibold text-[#1C1A17] m-0 overflow-hidden text-ellipsis whitespace-nowrap">
                                    {auth?.username}
                                </p>
                                <p className="text-[10px] text-[#A09890] m-0 uppercase font-semibold">
                                    {roleLabel}
                                </p>
                            </div>
                        )}
                        <button onClick={handleLogout} title="Sign out" aria-label="Sign out"
                            className="w-[30px] h-[30px] rounded-lg border border-[#E8E4DE] bg-white cursor-pointer flex items-center justify-center text-[#A09890] flex-shrink-0">
                            <LogOut size={13} />
                        </button>
                    </div>
                </div>
            </aside>

            {/* MAIN */}
            <main className="flex-1 flex flex-col min-w-0 bg-[#FAFAF9]">

                {/* Topbar */}
                <div className={`flex items-center gap-2 ${isMobile ? "px-3 py-3" : "px-7 py-4"} bg-white border-b border-[#E8E4DE]`}>
                    <h2 className={`${isMobile ? "text-base" : "text-[22px]"} font-bold text-[#1C1A17] m-0 tracking-[-0.01em] flex-shrink-0`}>
                        {activeTab === "books" ? "Books" : activeTab === "audio" ? "Audio" : "Videos"}
                    </h2>
                    <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-[#F5EDD8] text-[#B8922A] flex-shrink-0 font-semibold">
                        {activeTab === "books" ? bookTotal : activeTab === "audio" ? filteredAudio.length : filteredVideos.length}
                    </span>

                    <div className="ml-auto flex items-center gap-1.5">
                        <div className={`flex items-center gap-1.5 bg-[#F7F5F2] border border-[#E8E4DE] rounded-[10px] px-2.5 py-2 min-w-0 flex-1 ${isMobile ? "max-w-[140px]" : "max-w-[220px]"}`}>
                            <Search size={13} color="#A09890" className="flex-shrink-0" />
                            <input
                                type="text"
                                placeholder="Search..."
                                aria-label="Search"
                                value={search}
                                onChange={e => changeSearch(e.target.value)}
                                className="border-none outline-none text-[13px] text-[#1C1A17] [-webkit-text-fill-color:#1C1A17] bg-transparent w-full min-w-0 p-0 appearance-none"
                            />
                        </div>

                        {activeTab === "books" && (
                            <TagDropdown allTags={bookTagsList} selectedTags={selectedBookTags}
                                onToggle={tag => changeBookTags(toggled(selectedBookTags, tag))}
                                onClear={() => changeBookTags([])} />
                        )}
                        {activeTab === "videos" && (
                            <TagDropdown allTags={videoTagsList} selectedTags={selectedVideoTags}
                                onToggle={tag => setSelectedVideoTags(prev => toggled(prev, tag))}
                                onClear={() => setSelectedVideoTags([])} />
                        )}
                        {activeTab === "audio" && (
                            <TagDropdown allTags={audioTagsList} selectedTags={selectedAudioTags}
                                onToggle={tag => setSelectedAudioTags(prev => toggled(prev, tag))}
                                onClear={() => setSelectedAudioTags([])} />
                        )}

                        {canManage && (
                            <button onClick={() => setShowUpload(true)}
                                aria-label={`Upload ${activeTab === "books" ? "Book" : activeTab === "audio" ? "Audio" : "Video"}`}
                                className={`flex items-center ${isMobile ? "gap-0 px-2.5 py-2" : "gap-1.5 px-4 py-2"} bg-white hover:bg-[#F5EDD8] border-[1.5px] border-[#B8922A] rounded-[10px] text-[13px] font-semibold text-[#B8922A] cursor-pointer transition-colors whitespace-nowrap flex-shrink-0`}>
                                <Upload size={13} />
                                {!isMobile && ` Upload ${activeTab === "books" ? "Book" : activeTab === "audio" ? "Audio" : "Video"}`}
                            </button>
                        )}
                    </div>
                </div>

                {actionError && (
                    <div role="alert" className={`flex items-center gap-2 ${isMobile ? "mx-3 mt-3" : "mx-6 mt-4"} px-3.5 py-2.5 rounded-[10px] bg-[#FEF2F0] border border-[#FADADD] text-[13px] text-[#D94F3D]`}>
                        <span className="flex-1 min-w-0">{actionError}</span>
                        <button onClick={() => setActionError(null)} aria-label="Dismiss"
                            className="bg-transparent border-none cursor-pointer text-[#D94F3D] p-0 flex flex-shrink-0">
                            <X size={14} />
                        </button>
                    </div>
                )}

                {/* Grid */}
                <div className={`flex-1 overflow-y-auto ${isMobile ? "p-3" : "p-6"}`}>
                    {loading ? (
                        <div className="flex items-center justify-center h-full">
                            <Loader2 size={26} color="#B8922A" className="animate-spin" />
                        </div>
                    ) : tabError ? (
                        // A failed load must not look like an empty library.
                        <div role="alert" className="flex items-center justify-center h-full text-[13px] text-[#D94F3D] text-center">
                            {tabError}
                        </div>
                    ) : activeTab === "books" ? (
                        books.length === 0
                            ? <EmptyState icon={BookOpen} label="books" onUpload={() => setShowUpload(true)} canManage={canManage} />
                            : <>
                                <div className={`grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] ${isMobile ? "gap-2.5" : "gap-4"}`}>
                                    {books.map(book => (
                                        <BookGridCard key={book.uid} book={book} canManage={canManage}
                                            onDelete={refreshAfterBookChange}
                                            onEdit={setEditingBook}
                                            onError={setActionError} />
                                    ))}
                                </div>
                                {bookPages > 1 && (
                                    <div className="flex items-center justify-center gap-3 mt-5 text-[13px] text-[#6B6560]">
                                        <button onClick={() => setBookPage(p => p - 1)} disabled={bookPage <= 1} className={pagerButton}>
                                            Previous
                                        </button>
                                        <span>Page {bookPage} of {bookPages}</span>
                                        <button onClick={() => setBookPage(p => p + 1)} disabled={bookPage >= bookPages} className={pagerButton}>
                                            Next
                                        </button>
                                    </div>
                                )}
                            </>
                    ) : activeTab === "audio" ? (
                        filteredAudio.length === 0
                            ? <EmptyState icon={Music} label="audio" onUpload={() => setShowUpload(true)} canManage={canManage} />
                            : <div className={`grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] ${isMobile ? "gap-2.5" : "gap-4"}`}>
                                {filteredAudio.map(audio => (
                                    <AudioGridCard key={audio.id} audio={audio} canManage={canManage}
                                        onPlay={setCurrentlyPlayingAudio}
                                        currentlyPlaying={currentlyPlayingAudio}
                                        onDelete={id => setAudioTracks(prev => prev.filter(a => a.id !== id))}
                                        onUpdate={updated => setAudioTracks(prev => prev.map(a => a.id === updated.id ? updated : a))}
                                        onError={setActionError} />
                                ))}
                            </div>
                    ) : (
                        filteredVideos.length === 0
                            ? <EmptyState icon={Film} label="videos" onUpload={() => setShowUpload(true)} canManage={canManage} />
                            : <div className={`grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] ${isMobile ? "gap-2.5" : "gap-4"}`}>
                                {filteredVideos.map(video => (
                                    <VideoGridCard key={video.id} video={video} canManage={canManage}
                                        onPlay={setPlayingVideo}
                                        onDelete={id => setVideos(prev => prev.filter(v => v.id !== id))}
                                        onUpdate={updated => setVideos(prev => prev.map(v => v.id === updated.id ? updated : v))}
                                        onError={setActionError} />
                                ))}
                            </div>
                    )}
                </div>
            </main>

            {showUpload && canManage && (
                <UploadModal
                    type={uploadType}
                    onClose={() => setShowUpload(false)}
                    onSuccess={() => {
                        if (uploadType === "book") refreshAfterBookChange();
                        else if (uploadType === "audio") refreshAudio();
                        else refreshVideos();
                    }}
                />
            )}

            {editingBook && canManage && (
                <BookEditModal book={editingBook}
                    onClose={() => setEditingBook(null)}
                    onUpdate={() => {
                        setEditingBook(null);
                        refreshAfterBookChange();
                    }} />
            )}

            {showAddTeacher && isAdmin && <AddTeacherModal onClose={() => setShowAddTeacher(false)} />}

            {playingVideo && <VideoPlayerModal video={playingVideo} onClose={() => setPlayingVideo(null)} />}

            {auth?.first_login && (
                <ChangePasswordModal role={auth.role} onChanged={markPasswordChanged} onSignOut={handleLogout} />
            )}
        </div>
    );
};

export default Library;
