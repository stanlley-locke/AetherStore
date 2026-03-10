import React, { useState, useEffect, useRef } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { createAuthenticatedClient, messagingApi, storageApi, walletApi } from '../services/api';
import type { AetherObject } from '../services/api';
import { 
  Send, Paperclip, Search, Plus, Wallet, X, Users, 
  FileText, Download, Loader, Lock, Unlock
} from 'lucide-react';
import nacl from 'tweetnacl';
import './Chat.css';

interface UIMessage {
  id: string;
  sender: 'me' | 'them';
  plaintext?: string;
  encrypted_body?: string;
  timestamp: string;
  type: 'text' | 'transfer' | 'attachment' | 'system';
  isDecrypted?: boolean;
  amount?: number;
  attachmentId?: string;
  attachmentName?: string;
  rawId?: string;
  convId?: string;
}

interface UIConversation {
  id: string;
  name: string;
  latestSnippet: string;
  latestTime: string;
  unread: number;
  members?: string[];
}

export const Chat: React.FC = () => {
  const { did, privateKey, publicKey } = useAuthStore();
  const client = React.useMemo(() => did ? createAuthenticatedClient(did) : null, [did]);

  const [conversations, setConversations] = useState<UIConversation[]>([]);
  const [activeConvoId, setActiveConvoIdState] = useState<string | null>(localStorage.getItem('aetherchat_active_convo_id'));
  
  const setActiveConvoId = (id: string | null) => {
    setActiveConvoIdState(id);
    if (id) localStorage.setItem('aetherchat_active_convo_id', id);
    else localStorage.removeItem('aetherchat_active_convo_id');
  };
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  
  // Wallet state
  const [showSendAtk, setShowSendAtk] = useState(false);
  const [atkAmount, setAtkAmount] = useState('');
  const [isSendingAtk, setIsSendingAtk] = useState(false);
  
  // New convo state
  const [newConvoModal, setNewConvoModal] = useState(false);
  const [newConvoName, setNewConvoName] = useState('');
  const [newConvoParticipant, setNewConvoParticipant] = useState('');
  
  // Attachment state
  const [showAttachModal, setShowAttachModal] = useState(false);
  const [driveObjects, setDriveObjects] = useState<AetherObject[]>([]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeConvo = conversations.find(c => c.id === activeConvoId);

  const loadInbox = async (silent = false) => {
    if (!client) return;
    if (!silent) setLoading(true);
    try {
      const res = await messagingApi.getDHTInbox(client);
      const data = res.data;
      const convos: UIConversation[] = (data.conversations || []).map((c: any) => ({
        id: c.conversation_id,
        name: c.conversation_name || (c.members || []).find((m: string) => m !== did)?.slice(0, 12) || 'Unnamed Chat',
        latestSnippet: c.latest_message?.body
          ? `${c.latest_message.body.slice(0, 50)}...`
          : 'Encrypted message',
        latestTime: c.latest_message?.sent_at
          ? new Date(c.latest_message.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : '',
        unread: c.unread_count || 0,
        members: c.members || [],
      }));
      setConversations(convos);
      // Auto-select first if nothing is active (and no persisted state)
      if (convos.length > 0 && !activeConvoId && !silent) {
        setActiveConvoId(convos[0].id);
      }
    } catch (e: any) {
      console.error('Failed to load inbox:', e);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const loadMessages = async (convoId: string, silent = false) => {
    if (!client || !convoId) return;
    if (!silent) setMessagesLoading(true);
    try {
      const res = await messagingApi.getConversation(client, convoId);
      const backendMsgs = res.data.messages || [];
      
      const uiMsgs: UIMessage[] = backendMsgs.map((m: any) => {
        const normalizedMyDid = did?.startsWith('ath1') ? `did:aether:${did}` : did;
        const normalizedSenderDid = m.sender_did?.startsWith('ath1') ? `did:aether:${m.sender_did}` : m.sender_did;
        
        return {
          id: m.id,
          sender: normalizedSenderDid === normalizedMyDid ? 'me' : 'them',
          encrypted_body: m.encrypted_body,
          plaintext: m.plaintext,
          timestamp: new Date(m.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          type: m.message_type,
          attachmentId: m.attachment_id,
          attachmentName: m.attachment_name,
          isDecrypted: !!m.plaintext,
        };
      });
      
      setMessages(uiMsgs);
    } catch (e) {
      console.error('Failed to load messages:', e);
    } finally {
      if (!silent) setMessagesLoading(false);
    }
  };

  useEffect(() => {
    if (!client) return;
    loadInbox();
    const interval = setInterval(() => {
      loadInbox(true);
      if (activeConvoId) {
        loadMessages(activeConvoId, true);
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [client, activeConvoId]);

  useEffect(() => {
    if (activeConvoId) {
      loadMessages(activeConvoId);
    }
  }, [activeConvoId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeConvoId || sending) return;

    const text = input.trim();
    setInput('');
    setSending(true);

    const tempId = `temp-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: tempId, 
      sender: 'me', 
      plaintext: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      type: 'text',
      isDecrypted: true,
    }]);

    try {
      if (!client) return;
      await messagingApi.sendMessage(client, activeConvoId, text);
    } catch (e: any) {
      setMessages(prev => prev.filter(m => m.id !== tempId));
      alert(e.response?.data?.error || 'Failed to send message.');
    } finally {
      setSending(false);
    }
  };

  const handleDecrypt = async (msgId: string) => {
    if (!client || !activeConvoId) return;
    try {
      const res = await messagingApi.decryptMessage(client, activeConvoId, msgId);
      setMessages(prev => prev.map(m => 
        m.id === msgId ? { ...m, plaintext: res.data.plaintext, isDecrypted: true } : m
      ));
    } catch (e: any) {
      alert('Decryption failed. You might not have the keys for this message.');
    }
  };

  const sendAtk = async () => {
    const amount = parseFloat(atkAmount);
    if (isNaN(amount) || amount <= 0 || !activeConvo) return;
    try {
      if (!client) return;
      setIsSendingAtk(true);
      const detailRes = await messagingApi.getConversation(client, activeConvo.id);
      const members = detailRes.data.conversation.members;
      const recipientDid = members.find((m: string) => m !== did) || 'ath1prototype';
      
      const timestamp = Math.floor(Date.now() / 1000).toString();
      const message = `${recipientDid}:${atkAmount}:${timestamp}`;
      
      const privBytes = new Uint8Array(privateKey!.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16)));
      const msgBytes = new TextEncoder().encode(message);
      const keyPair = nacl.sign.keyPair.fromSeed(privBytes);
      const signatureBytes = nacl.sign.detached(msgBytes, keyPair.secretKey);
      const signature = Array.from(signatureBytes).map(b => b.toString(16).padStart(2, '0')).join('');

      await walletApi.transfer(client, {
        public_key: publicKey!,
        recipient_address: recipientDid,
        amount: atkAmount,
        timestamp,
        signature,
      });

      setMessages(prev => [...prev, {
        id: `transfer-${Date.now()}`,
        sender: 'me',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'transfer',
        amount,
        isDecrypted: true,
      }]);
      setAtkAmount('');
      setShowSendAtk(false);
      
      try {
        await messagingApi.sendMessage(client, activeConvo.id, `[ATK Transfer] Sent ${amount} ATK via AetherWallet`);
      } catch (_) {}
      
    } catch (e: any) {
      alert(e.response?.data?.error || 'Transfer failed.');
    } finally {
      setIsSendingAtk(false);
    }
  };

  const createConversation = async () => {
    if (!newConvoName.trim() || !newConvoParticipant.trim() || !client) return;
    try {
      const uniqueDIDs = Array.from(new Set(newConvoParticipant.split(',').map(p => p.trim()).filter(Boolean)));
      const res = await messagingApi.createConversation(client, uniqueDIDs, newConvoName.trim());
      setNewConvoModal(false);
      setNewConvoName(''); setNewConvoParticipant('');
      await loadInbox();
      setActiveConvoId(res.data.id);
    } catch (e: any) {
      alert(e.response?.data?.error || 'Failed to create conversation.');
    }
  };

  const loadDriveObjects = async () => {
    if (!client) return;
    try {
      const res = await storageApi.listObjects(client, { page: 1, page_size: 50 });
      setDriveObjects(res.data.objects || []);
    } catch (e) {
      console.error('Failed to load drive objects:', e);
    }
  };

  const openAttachModal = () => {
    setShowAttachModal(true);
    loadDriveObjects();
  };

  const sendAttachment = async (obj: AetherObject) => {
    setShowAttachModal(false);
    if (!activeConvoId) return;
    setMessages(prev => [...prev, {
      id: `attach-${Date.now()}`,
      sender: 'me',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      type: 'attachment',
      attachmentId: obj.id,
      attachmentName: obj.filename || obj.id,
      isDecrypted: true,
    }]);
    try {
      if (!client) return;
      await messagingApi.sendMessage(client, activeConvoId, `[Attachment] ${obj.filename || obj.id}`, obj.id);
    } catch (e: any) {
      alert('Failed to send attachment.');
    }
  };

  const handleDownloadAttachment = async (objId: string) => {
    if (!client) return;
    try {
      await storageApi.startDownload(client, objId);
      alert(`Download queued.`);
    } catch (e: any) {
      alert('Download request failed.');
    }
  };

  return (
    <div className="chat-container">
      <aside className="chat-sidebar">
        <div className="chat-sidebar-header">
          <h2>AetherChat</h2>
          <button className="icon-round-btn" onClick={() => setNewConvoModal(true)} title="New Conversation">
            <Plus size={18} />
          </button>
        </div>
        <div className="chat-search-wrap">
          <Search size={15} className="chat-search-icon" />
          <input type="text" placeholder="Search conversations..." className="chat-search-input" />
        </div>
        <div className="convo-list">
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>
          ) : (
            conversations.map(convo => (
              <div
                key={convo.id}
                className={`convo-item ${activeConvoId === convo.id ? 'active' : ''}`}
                onClick={() => setActiveConvoId(convo.id)}
              >
                <div className="convo-avatar">{(convo.name || '?').charAt(0).toUpperCase()}</div>
                <div className="convo-info">
                  <div className="convo-top">
                    <span className="convo-name">{convo.name}</span>
                    <span className="convo-time">{convo.latestTime}</span>
                  </div>
                  <p className="convo-preview">{convo.latestSnippet}</p>
                </div>
                {convo.unread > 0 && <span className="unread-badge">{convo.unread}</span>}
              </div>
            ))
          )}
        </div>
      </aside>

      <div className="chat-window">
        {!activeConvoId ? (
          <div className="chat-placeholder">
            <div className="glass-panel" style={{ padding: '3rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
              <Users size={64} style={{ color: 'var(--accent)', opacity: 0.5 }} />
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>Decentralized Communications</h3>
              <p style={{ margin: 0, textAlign: 'center', maxWidth: '250px' }}>Select a conversation from the sidebar to start chatting securely on the Aether network.</p>
              <button className="primary-button" style={{ marginTop: '1rem' }} onClick={() => setNewConvoModal(true)}>
                <Plus size={18} /> New Conversation
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="chat-window-header">
              <div className="chat-header-info">
                <div className="convo-avatar sm">{(activeConvo?.name || '?').charAt(0).toUpperCase()}</div>
                <div>
                  <p className="chat-contact-name">{activeConvo?.name}</p>
                  <p className="chat-contact-id">{activeConvoId?.slice(0, 12)}... · E2E Encrypted</p>
                </div>
              </div>
              <button className="chat-atk-btn" onClick={() => setShowSendAtk(!showSendAtk)}>
                <Wallet size={15} /> Send ATK
              </button>
            </div>

            {showSendAtk && (
              <div className="atk-panel">
                <input type="number" placeholder="Amount (ATK)" value={atkAmount} onChange={e => setAtkAmount(e.target.value)} className="atk-input" />
                <button className="chat-send-main" onClick={sendAtk} disabled={isSendingAtk}>
                  {isSendingAtk ? <Loader size={16} className="spinner-icon" /> : 'Send'}
                </button>
              </div>
            )}

            <div className="messages-area">
              {messagesLoading && messages.length === 0 ? (
                <div style={{ textAlign: 'center' }}><Loader className="spinner-icon" /></div>
              ) : (
                messages.map(msg => (
                  <div key={msg.id} className={`msg-wrapper ${msg.sender === 'me' ? 'out' : 'in'}`}>
                    <div className="msg-row">
                      {msg.type === 'transfer' ? (
                        <div className="transfer-card">
                          <Wallet size={18} color="var(--accent)" />
                          <div>
                            <p className="transfer-amount">{msg.amount} ATK</p>
                            <p className="transfer-label">{msg.sender === 'me' ? 'Sent' : 'Received'}</p>
                          </div>
                        </div>
                      ) : msg.type === 'attachment' ? (
                        <div className="attachment-card">
                          <FileText size={20} />
                          <div className="attachment-info">
                            <span className="attachment-name">{msg.attachmentName}</span>
                          </div>
                          <button className="decrypt-btn" onClick={() => handleDownloadAttachment(msg.attachmentId!)}><Download size={14}/></button>
                        </div>
                      ) : msg.type === 'system' ? (
                        <div className="system-msg">{msg.plaintext}</div>
                      ) : (
                        <div className="msg-bubble-wrap">
                          <div className={`msg-bubble ${!msg.isDecrypted ? 'encrypted' : ''}`}>
                            <p>{msg.isDecrypted ? msg.plaintext : `Encrypted: ${msg.encrypted_body?.slice(0, 20)}...`}</p>
                            <span className="msg-time">{msg.timestamp}</span>
                          </div>
                          {!msg.isDecrypted && (
                            <button className="decrypt-btn" onClick={() => handleDecrypt(msg.id)}><Lock size={14}/></button>
                          )}
                          {msg.isDecrypted && <div className="decrypted-badge"><Unlock size={10} /></div>}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-input-area" onSubmit={sendMessage}>
              <button type="button" className="chat-attach-btn" onClick={openAttachModal}><Paperclip size={18} /></button>
              <input className="chat-text-input" value={input} onChange={e => setInput(e.target.value)} placeholder="Send encrypted message..." />
              <button type="submit" className="chat-send-main" disabled={!input.trim() || sending}><Send size={17} /></button>
            </form>
          </>
        )}
      </div>

      {newConvoModal && (
        <div className="modal-overlay" onClick={() => setNewConvoModal(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0 }}>New Conversation</h3>
              <button onClick={() => setNewConvoModal(false)}><X size={20} /></button>
            </div>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', display: 'block' }}>Conversation Name</label>
            <input className="modal-input" placeholder="e.g. Project Aether" value={newConvoName} onChange={e => setNewConvoName(e.target.value)} />
            <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', display: 'block' }}>Participants (Comma-separated DIDs)</label>
            <input className="modal-input" placeholder="did:aether:..., did:aether:..." value={newConvoParticipant} onChange={e => setNewConvoParticipant(e.target.value)} />
            <button className="drive-btn-primary" onClick={createConversation}>Start Conversation</button>
          </div>
        </div>
      )}

      {showAttachModal && (
        <div className="modal-overlay" onClick={() => setShowAttachModal(false)}>
          <div className="modal-card" style={{ width: 500 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0 }}><Paperclip size={18} style={{ verticalAlign: 'middle', marginRight: '6px' }} /> Attach File</h3>
              <button onClick={() => setShowAttachModal(false)}><X size={20} /></button>
            </div>
            <p style={{ margin: '0 0 1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Select a file from your securely encrypted AetherDrive.
            </p>
            <div style={{ maxHeight: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {driveObjects.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Drive is empty.</div>
              ) : (
                driveObjects.map(obj => (
                  <div key={obj.id} className="attachment-select-item" style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.8rem', background: 'var(--bg-secondary)', borderRadius: '10px', cursor: 'pointer' }} onClick={() => sendAttachment(obj)}>
                    <FileText size={16} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{obj.filename || obj.id.slice(0, 12)}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{(obj.size / 1024).toFixed(1)} KB</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
