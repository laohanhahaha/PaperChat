import { useNavigate } from 'react-router-dom';
import styles from './NotFoundPage.module.css';

function NotFoundPage() {
    const navigate = useNavigate();

    return (
        <div className={styles.container}>
            <div className={styles.content}>
                <div className={styles.icon}>🔍</div>
                <h1 className={styles.title}>404</h1>
                <h2 className={styles.subtitle}>页面未找到</h2>
                <p className={styles.description}>
                    抱歉，您访问的页面不存在或已被移除
                </p>
                <div className={styles.actions}>
                    <button 
                        className={styles.primaryBtn}
                        onClick={() => navigate('/papers')}
                    >
                        返回首页
                    </button>
                    <button 
                        className={styles.secondaryBtn}
                        onClick={() => navigate(-1)}
                    >
                        返回上一页
                    </button>
                </div>
            </div>
        </div>
    );
}

export default NotFoundPage;
