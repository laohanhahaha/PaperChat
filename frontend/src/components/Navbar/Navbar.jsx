import { useLocation, useNavigate } from 'react-router-dom';
import styles from './Navbar.module.css';

const navItems = [
    { path: '/chat', icon: '💬', label: '聊天' },
    { path: '/papers', icon: '📚', label: '论文库' },
    { path: '/knowledge', icon: '💡', label: '知识库' },
    { path: '/writing', icon: '✍️', label: '写作辅助' },
];

function Navbar() {
    const location = useLocation();
    const navigate = useNavigate();

    return (
        <nav className={styles.navbar}>
            <div className={styles.logo}>
                <span className={styles.logoIcon}>📖</span>
                <span className={styles.logoText}>PaperChat</span>
            </div>

            <div className={styles.navItems}>
                {navItems.map(item => (
                    <div
                        key={item.path}
                        className={`${styles.navItem} ${location.pathname === item.path ? styles.active : ''}`}
                        onClick={() => navigate(item.path)}
                        title={item.label}
                    >
                        <span className={styles.navIcon}>{item.icon}</span>
                        <span className={styles.navLabel}>{item.label}</span>
                    </div>
                ))}
            </div>

            <div className={styles.userSection}>
                <div
                    className={`${styles.navItem} ${location.pathname === '/settings' ? styles.active : ''}`}
                    onClick={() => navigate('/settings')}
                    title="系统设置"
                >
                    <span className={styles.navIcon}>⚙️</span>
                    <span className={styles.navLabel}>设置</span>
                </div>
                <div className={styles.userName} title="个人工作区">
                    个人工作区
                </div>
            </div>
        </nav>
    );
}

export default Navbar;
