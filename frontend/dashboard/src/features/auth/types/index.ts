export interface LoginRequest {
    username: string;
    password: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
}

export interface RegisterRequest {
    username: string;
    password: string;
    role?: string;
}

export interface UserResponse {
    id: string;
    username: string;
    role: string;
}

export interface UserListItem {
    id: string;
    username: string;
    role: string;
    created_at: string;
}

export interface UsersListResponse {
    users: UserListItem[];
    total: number;
}

export interface WsTicketResponse {
    ticket: string;
    expires_in: number;
    ws_url: string;
}
